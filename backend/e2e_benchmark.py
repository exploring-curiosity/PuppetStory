"""
Child Interruption Benchmark for PuppetStory

Measures what actually matters: after a child interrupts the narration,
how quickly does the system:
  1. Resume audio narration (incorporating the child's input)
  2. Update the puppet stage (set_scene / action_sequence reflecting changes)

Tests 3 interruption types:
  - CHANGE REQUEST: "Make the wolf friendly!" → needs scene/character adaptation
  - QUESTION: "Why did the pig use straw?" → needs answer + puppet demonstration
  - SUGGESTION: "The pig should do a silly dance!" → needs animation + narration

Each interruption is sent AFTER audio is flowing (story is active).
We measure from the moment child text is sent to:
  - first_audio_resume: time until new audio bytes arrive
  - first_scene_update: time until set_scene fires (if applicable)
  - first_animation:    time until action_sequence fires
  - narration_content:  log of what the narrator says (for manual review)
"""

import asyncio
import json
import os
import sys
import time
import traceback

import websockets
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ─── Configuration ───────────────────────────────────────────────────────

BACKEND_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/story"
STORY_ID = "three_little_pigs"
MAX_DURATION = 180  # seconds — longer to allow all interruptions

# Each interruption: (type, text, min_delay_after_prev_audio)
# min_delay_after_prev_audio: wait this many seconds AFTER story audio starts
# before sending this interruption. Ensures the story is flowing.
INTERRUPTIONS = [
    {
        "type": "change_request",
        "text": "Make the wolf really friendly! He should be a nice wolf who just wants to be friends with the pigs!",
        "delay_after_audio": 30,  # 30s after first audio
        "expect_scene_update": True,
        "expect_animation": True,
    },
    {
        "type": "question",
        "text": "Why did the little pig build his house out of straw? That seems like a bad idea!",
        "delay_after_prev": 30,  # 30s after previous interruption resolves
        "expect_scene_update": False,  # question may not need scene change
        "expect_animation": True,      # puppet should gesture/react
    },
    {
        "type": "suggestion",
        "text": "Can you make all the pigs do a silly dance right now?",
        "delay_after_prev": 30,
        "expect_scene_update": False,
        "expect_animation": True,  # definitely needs animation
    },
]

# Parse CLI args
for arg in sys.argv[1:]:
    if arg.startswith("--story="):
        STORY_ID = arg.split("=", 1)[1]
    elif arg.startswith("--duration="):
        MAX_DURATION = int(arg.split("=", 1)[1])


# ─── Interruption Result Tracker ─────────────────────────────────────────

class InterruptionResult:
    """Track metrics for a single child interruption."""
    def __init__(self, itype: str, text: str):
        self.type = itype
        self.text = text
        self.send_time = None       # absolute monotonic time when sent
        self.audio_resume_t = None  # time to first audio after send
        self.scene_update_t = None  # time to first set_scene after send
        self.animation_t = None     # time to first action_sequence after send
        self.narration_words = []   # words the narrator said in response
        self.scene_data = None      # the set_scene data received
        self.animation_data = None  # the action_sequence data received
        self.resolved = False       # True once audio resumes

    def mark_sent(self):
        self.send_time = time.monotonic()

    def on_audio_resume(self):
        if self.send_time and self.audio_resume_t is None:
            self.audio_resume_t = time.monotonic() - self.send_time
            self.resolved = True

    def on_scene_update(self, data: dict):
        if self.send_time and self.scene_update_t is None:
            self.scene_update_t = time.monotonic() - self.send_time
            self.scene_data = data

    def on_animation(self, data: dict):
        if self.send_time and self.animation_t is None:
            self.animation_t = time.monotonic() - self.send_time
            self.animation_data = data

    def add_narration(self, text: str):
        self.narration_words.append(text)

    def summary_str(self) -> str:
        lines = []
        lines.append(f"    Type: {self.type}")
        lines.append(f"    Text: \"{self.text[:70]}\"")
        if self.audio_resume_t is not None:
            grade = "✅" if self.audio_resume_t < 3 else "⚠️" if self.audio_resume_t < 6 else "❌"
            lines.append(f"    {grade} Audio resume:    {self.audio_resume_t:.3f}s")
        else:
            lines.append(f"    ❌ Audio resume:    NO RESPONSE")
        if self.scene_update_t is not None:
            grade = "✅" if self.scene_update_t < 5 else "⚠️" if self.scene_update_t < 10 else "❌"
            bg = self.scene_data.get("background_id", "?") if self.scene_data else "?"
            mood = self.scene_data.get("mood", "?") if self.scene_data else "?"
            lines.append(f"    {grade} Scene update:    {self.scene_update_t:.3f}s (bg={bg}, mood={mood})")
        else:
            lines.append(f"    ⚠️  Scene update:    none")
        if self.animation_t is not None:
            grade = "✅" if self.animation_t < 5 else "⚠️" if self.animation_t < 10 else "❌"
            puppets = list(self.animation_data.get("puppets", {}).keys()) if self.animation_data else []
            lines.append(f"    {grade} Animation:       {self.animation_t:.3f}s (puppets={puppets})")
        else:
            lines.append(f"    ⚠️  Animation:       none")
        # Show first 100 chars of narration response
        narration = "".join(self.narration_words).strip()
        if narration:
            lines.append(f"    📝 Response: \"{narration[:120]}\"")
        else:
            lines.append(f"    📝 Response: (no narration captured)")
        return "\n".join(lines)


class BenchmarkResults:
    def __init__(self):
        self.t0 = time.monotonic()
        self.events = []
        self.first_audio_t = None
        self.first_scene_t = None
        self.first_action_t = None
        self.audio_chunks = 0
        self.audio_bytes = 0
        self.total_scenes = 0
        self.total_animations = 0
        self.interruption_results: list[InterruptionResult] = []
        self._active_interruption: InterruptionResult | None = None
        self.last_audio_t = None
        self.transcripts = []

    def elapsed(self) -> float:
        return time.monotonic() - self.t0

    def log(self, event: str, **kwargs):
        t = self.elapsed()
        self.events.append({"t": round(t, 3), "event": event, **kwargs})
        extra = ""
        if kwargs:
            parts = [f"{k}={v}" for k, v in kwargs.items()]
            extra = " | " + ", ".join(parts)
        print(f"  [{t:7.3f}s] {event}{extra}")

    def start_interruption(self, result: InterruptionResult):
        self._active_interruption = result
        self.interruption_results.append(result)

    def on_audio(self, data: bytes):
        now = self.elapsed()
        if self.first_audio_t is None:
            self.first_audio_t = now
            self.log("FIRST_AUDIO_BYTE", latency_s=round(now, 3))
        self.audio_chunks += 1
        self.audio_bytes += len(data)
        self.last_audio_t = now

        # If there's an active interruption waiting for audio resume
        if self._active_interruption and not self._active_interruption.resolved:
            self._active_interruption.on_audio_resume()
            latency = self._active_interruption.audio_resume_t
            self.log("INTERRUPTION_AUDIO_RESUME",
                     type=self._active_interruption.type,
                     latency_s=round(latency, 3))

    def on_set_scene(self, data: dict):
        now = self.elapsed()
        self.total_scenes += 1
        if self.first_scene_t is None:
            self.first_scene_t = now
            self.log("FIRST_SET_SCENE", latency_s=round(now, 3), bg=data.get("background_id"))
        else:
            self.log("SET_SCENE", bg=data.get("background_id"), mood=data.get("mood"))

        if self._active_interruption and self._active_interruption.send_time:
            self._active_interruption.on_scene_update(data)
            if self._active_interruption.scene_update_t:
                self.log("INTERRUPTION_SCENE_UPDATE",
                         type=self._active_interruption.type,
                         latency_s=round(self._active_interruption.scene_update_t, 3))

    def on_action_sequence(self, data: dict):
        now = self.elapsed()
        self.total_animations += 1
        if self.first_action_t is None:
            self.first_action_t = now
            self.log("FIRST_ACTION_SEQ", latency_s=round(now, 3))
        else:
            self.log("ACTION_SEQ", dur=data.get("duration"),
                     puppets=list(data.get("puppets", {}).keys()))

        if self._active_interruption and self._active_interruption.send_time:
            self._active_interruption.on_animation(data)
            if self._active_interruption.animation_t:
                self.log("INTERRUPTION_ANIMATION",
                         type=self._active_interruption.type,
                         latency_s=round(self._active_interruption.animation_t, 3))

    def on_transcript(self, role: str, text: str):
        self.transcripts.append({"t": round(self.elapsed(), 3), "role": role, "text": text})
        self.log(f"TRANSCRIPT_{role.upper()}", text=text[:90])

        # Capture narration after an interruption for content review
        if role == "narrator" and self._active_interruption and self._active_interruption.send_time:
            self._active_interruption.add_narration(text)

    def print_summary(self):
        dur = self.elapsed()
        print("\n" + "═" * 72)
        print("  🎭  CHILD INTERRUPTION BENCHMARK RESULTS")
        print("═" * 72)
        print(f"\n  Story:    {STORY_ID}")
        print(f"  Duration: {dur:.1f}s")

        print(f"\n  ─── Initial Setup ───")
        if self.first_audio_t is not None:
            print(f"  Time to first audio:     {self.first_audio_t:.3f}s")
        if self.first_scene_t is not None:
            print(f"  Time to first scene:     {self.first_scene_t:.3f}s")
        if self.first_action_t is not None:
            print(f"  Time to first animation: {self.first_action_t:.3f}s")

        audio_dur = self.audio_bytes / (24000 * 2) if self.audio_bytes else 0
        print(f"\n  ─── Overall Stats ───")
        print(f"  Total audio:      ~{audio_dur:.1f}s of narration")
        print(f"  Total scenes:     {self.total_scenes}")
        print(f"  Total animations: {self.total_animations}")

        print(f"\n  ═══ CHILD INTERRUPTION RESULTS ({len(self.interruption_results)} interruptions) ═══")
        for i, ir in enumerate(self.interruption_results):
            print(f"\n  ── Interruption #{i+1} ──")
            print(ir.summary_str())

        # Summary table
        print(f"\n  ─── Summary Table ───")
        print(f"  {'Type':<20} {'Audio Resume':>14} {'Scene Update':>14} {'Animation':>14}")
        print(f"  {'─'*20} {'─'*14} {'─'*14} {'─'*14}")
        for ir in self.interruption_results:
            ar = f"{ir.audio_resume_t:.3f}s" if ir.audio_resume_t else "N/A"
            su = f"{ir.scene_update_t:.3f}s" if ir.scene_update_t else "N/A"
            an = f"{ir.animation_t:.3f}s" if ir.animation_t else "N/A"
            print(f"  {ir.type:<20} {ar:>14} {su:>14} {an:>14}")

        # Averages
        audio_times = [ir.audio_resume_t for ir in self.interruption_results if ir.audio_resume_t]
        if audio_times:
            avg = sum(audio_times) / len(audio_times)
            grade = "✅" if avg < 3 else "⚠️" if avg < 6 else "❌"
            print(f"\n  {grade} Avg audio resume: {avg:.3f}s")
        anim_times = [ir.animation_t for ir in self.interruption_results if ir.animation_t]
        if anim_times:
            avg = sum(anim_times) / len(anim_times)
            grade = "✅" if avg < 5 else "⚠️" if avg < 10 else "❌"
            print(f"  {grade} Avg animation:    {avg:.3f}s")

        print("\n" + "═" * 72)


# ─── Main Benchmark ──────────────────────────────────────────────────────

async def run_benchmark():
    import aiohttp

    results = BenchmarkResults()

    # ─── Step 1: Generate assets ─────────────────────────────────────────
    print("\n📦 Step 1: Generating story assets...")
    t0 = time.monotonic()
    async with aiohttp.ClientSession() as http:
        async with http.post(f"{BACKEND_URL}/api/stories/{STORY_ID}/generate-assets") as resp:
            async for line in resp.content:
                text = line.decode().strip()
                if text.startswith("data: "):
                    evt = json.loads(text[6:])
                    if evt.get("event") in ("progress", "cached"):
                        sys.stdout.write(f"\r  Generating... {evt.get('done', '?')}/{evt.get('total', '?')} ")
                        sys.stdout.flush()
                    if evt.get("event") == "complete":
                        break
    asset_time = time.monotonic() - t0
    print(f"\n  ✅ Assets ready in {asset_time:.3f}s")
    results.log("ASSETS_GENERATED", duration_s=round(asset_time, 3))

    # ─── Step 2: WebSocket session ───────────────────────────────────────
    print(f"\n🔌 Step 2: Connecting to {WS_URL} with story={STORY_ID}")
    results.log("WS_CONNECTING")

    stop_event = asyncio.Event()
    audio_started = asyncio.Event()  # set when first audio arrives

    async with websockets.connect(WS_URL, max_size=10_000_000) as ws:
        await ws.send(json.dumps({"type": "init", "story_id": STORY_ID}))
        results.log("WS_INIT_SENT")

        # ── Child interruption scheduler ─────────────────────────────────
        async def interruption_loop():
            # Wait for story audio to start flowing before interrupting
            results.log("WAITING_FOR_AUDIO_START")
            await audio_started.wait()
            results.log("AUDIO_STARTED_SCHEDULING_INTERRUPTIONS")

            for i, interruption in enumerate(INTERRUPTIONS):
                if stop_event.is_set():
                    return

                # Determine delay
                if i == 0:
                    delay = interruption.get("delay_after_audio", 30)
                else:
                    delay = interruption.get("delay_after_prev", 30)

                results.log(f"WAITING_{delay}s_BEFORE_INTERRUPTION_{i+1}",
                           type=interruption["type"])
                await asyncio.sleep(delay)
                if stop_event.is_set():
                    return

                # Send the interruption
                ir = InterruptionResult(interruption["type"], interruption["text"])
                results.start_interruption(ir)
                ir.mark_sent()

                results.log("CHILD_INTERRUPTION_SENT",
                           type=interruption["type"],
                           text=interruption["text"][:50])
                await ws.send(json.dumps({
                    "type": "user_text",
                    "text": interruption["text"]
                }))

                # Wait for resolution (audio resumes) or timeout
                deadline = time.monotonic() + 45  # 45s max wait per interruption
                while not ir.resolved and time.monotonic() < deadline:
                    if stop_event.is_set():
                        return
                    await asyncio.sleep(0.2)

                if ir.resolved:
                    results.log("INTERRUPTION_RESOLVED", type=interruption["type"])
                    # Let the narration flow for a bit to capture response content
                    await asyncio.sleep(8)
                    # Clear active interruption so we don't capture unrelated narration
                    results._active_interruption = None
                else:
                    results.log("INTERRUPTION_TIMEOUT", type=interruption["type"])
                    results._active_interruption = None

        # ── Timeout ──────────────────────────────────────────────────────
        async def timeout_watcher():
            await asyncio.sleep(MAX_DURATION)
            results.log("MAX_DURATION_REACHED")
            stop_event.set()

        interruption_task = asyncio.create_task(interruption_loop())
        timeout_task = asyncio.create_task(timeout_watcher())

        # ── Receive loop ─────────────────────────────────────────────────
        try:
            while not stop_event.is_set():
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    results.log("WS_CLOSED")
                    break

                if isinstance(msg, bytes):
                    results.on_audio(msg)
                    if not audio_started.is_set():
                        audio_started.set()
                else:
                    try:
                        data = json.loads(msg)
                        mtype = data.get("type")
                        if mtype == "set_scene":
                            results.on_set_scene(data.get("data", {}))
                        elif mtype == "action_sequence":
                            results.on_action_sequence(data.get("data", {}))
                        elif mtype == "transcript":
                            results.on_transcript(data.get("role", "?"), data.get("text", ""))
                        elif mtype == "narration_text":
                            results.on_transcript("narrator", data.get("text", ""))
                        elif mtype == "thinking":
                            results.log("THINKING", text=data.get("text", "")[:40])
                        elif mtype == "turn_complete":
                            results.log("TURN_COMPLETE")
                        elif mtype == "error":
                            results.log("SERVER_ERROR", msg=data.get("message"))
                            break
                    except json.JSONDecodeError:
                        pass

        except KeyboardInterrupt:
            results.log("INTERRUPTED_BY_USER")
        finally:
            stop_event.set()
            interruption_task.cancel()
            timeout_task.cancel()
            for task in [interruption_task, timeout_task]:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    results.log("BENCHMARK_DONE")
    results.print_summary()


if __name__ == "__main__":
    print("═" * 72)
    print("  🎭  CHILD INTERRUPTION BENCHMARK")
    print(f"  Story: {STORY_ID}  |  Max Duration: {MAX_DURATION}s")
    print(f"  Interruptions: {len(INTERRUPTIONS)}")
    for i, intr in enumerate(INTERRUPTIONS):
        print(f"    #{i+1} [{intr['type']}]: \"{intr['text'][:60]}\"")
    print("═" * 72)
    asyncio.run(run_benchmark())
