"""
End-to-end test for Dream Weaver backend.
Tests the full pipeline: Live API session → voice narration → function calling → image generation stub.

Simulates a short story session with text inputs (no mic needed):
1. Start session → AI greets
2. Child says "a pink dragon!" → AI narrates + generates scene
3. Child interrupts "the dragon should blow bubbles!" → AI pivots + updates scene
4. Parent says "sleepy time" → AI winds down

Run: python test_e2e.py
"""

import asyncio
import json
import os
import wave
import sys
import time
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from live_session import LiveSession
from image_generator import ImageGenerator
from google.genai import types

# Collect stats
stats = {
    "audio_chunks": 0,
    "audio_bytes": 0,
    "scenes_received": 0,
    "scenes": [],
    "transcripts": [],
    "errors": [],
    "turn_complete_count": 0,
}

# Shared state
session = None
image_generator = None
audio_file = None
turn_complete_event = None


def open_audio_file():
    global audio_file
    audio_file = wave.open("test_output.wav", "wb")
    audio_file.setnchannels(1)
    audio_file.setsampwidth(2)  # 16-bit
    audio_file.setframerate(24000)  # Gemini outputs 24kHz


def close_audio_file():
    global audio_file
    if audio_file:
        audio_file.close()
        audio_file = None


async def on_audio(data: bytes):
    """Collect audio output."""
    stats["audio_chunks"] += 1
    stats["audio_bytes"] += len(data)
    if audio_file:
        audio_file.writeframes(data)


async def on_tool_call(tool_call):
    """Handle generate_scene function calls."""
    for fc in tool_call.function_calls:
        if fc.name == "generate_scene":
            try:
                if isinstance(fc.args, str):
                    scene_data = json.loads(fc.args)
                elif isinstance(fc.args, dict):
                    scene_data = fc.args
                else:
                    # google.protobuf.struct_pb2.Struct or similar
                    scene_data = dict(fc.args)
            except Exception as e:
                print(f"  ⚠️  Could not parse function args: {e}")
                scene_data = {"scene_title": "parse_error", "mood": "calm", "transition": "fade", "elements": []}

            scene_title = scene_data.get("scene_title", "untitled")
            mood = scene_data.get("mood", "?")
            elements = scene_data.get("elements", [])
            new_count = sum(1 for e in elements if e.get("is_new"))
            cached_count = len(elements) - new_count

            print(f"\n  🎨 SCENE: \"{scene_title}\"")
            print(f"     Mood: {mood} | Elements: {len(elements)} ({new_count} new, {cached_count} cached)")
            for el in elements:
                anim = el.get("animation", {})
                print(f"     - [{el.get('id')}] z:{el.get('z_index')} pos:({el.get('position_x')},{el.get('position_y')}) "
                      f"anim:{anim.get('type','?')}({anim.get('speed','?')}) new:{el.get('is_new')}")

            # Process through image generator stub
            scene_with_images = await image_generator.process_scene(scene_data)
            stats["scenes_received"] += 1
            stats["scenes"].append({
                "title": scene_title,
                "mood": mood,
                "element_count": len(elements),
                "new_elements": new_count,
            })

            # Send function response back to Gemini
            try:
                response = types.FunctionResponse(
                    id=fc.id,
                    name=fc.name,
                    response={"result": "Scene displayed successfully", "scheduling": "SILENT"}
                )
                await session.session.send_tool_response(function_responses=[response])
            except Exception as e:
                print(f"  ⚠️  Could not send tool response: {e}")


async def on_transcript(text: str, role: str):
    """Collect transcriptions."""
    prefix = "🗣️  NARRATOR" if role == "narrator" else "👦 USER"
    print(f"  {prefix}: {text}")
    stats["transcripts"].append({"role": role, "text": text})


async def send_and_wait(text: str, wait_seconds: int = 10):
    """Send text and wait for the AI to respond."""
    try:
        await session.send_text(text)
    except Exception as e:
        print(f"  ⚠️  Send failed: {e}")
        stats["errors"].append(str(e))
        return

    # Wait for the response (audio + possible function calls)
    start = time.time()
    initial_chunks = stats["audio_chunks"]
    initial_scenes = stats["scenes_received"]

    # Wait at least wait_seconds, but check for activity
    await asyncio.sleep(wait_seconds)

    new_chunks = stats["audio_chunks"] - initial_chunks
    new_scenes = stats["scenes_received"] - initial_scenes
    elapsed = time.time() - start
    print(f"  ⏱️  Wait complete ({elapsed:.1f}s): +{new_chunks} audio chunks, +{new_scenes} scenes")


async def story_script(live: LiveSession):
    """The story script that runs after the session is connected."""
    # Give the session a moment to stabilize
    await asyncio.sleep(2)

    print("─" * 60)
    print("STEP 1: Greeting — 'Hello! I'm ready for a bedtime story!'")
    print("─" * 60)
    await send_and_wait("Hello! I'm ready for a bedtime story!", wait_seconds=12)

    print("\n" + "─" * 60)
    print("STEP 2: Child — 'I want a story about a pink dragon on a mountain!'")
    print("─" * 60)
    await send_and_wait(
        "I want a story about a friendly pink dragon that lives on top of a snowy mountain!",
        wait_seconds=15
    )

    print("\n" + "─" * 60)
    print("STEP 3: Child interrupts — 'The dragon should blow BUBBLES!'")
    print("─" * 60)
    await send_and_wait(
        "No wait! The dragon should blow rainbow BUBBLES instead of fire! And the bubbles make flowers grow!",
        wait_seconds=15
    )

    print("\n" + "─" * 60)
    print("STEP 4: Parent — 'Sleepy time'")
    print("─" * 60)
    await send_and_wait(
        "[PARENT SIGNAL: sleepy time] — Please begin winding down the story. "
        "Slow your pace, use calming imagery, and bring the adventure to a peaceful, cozy conclusion.",
        wait_seconds=15
    )

    # Signal session to stop
    await live.stop()


async def run_story_test():
    global session, image_generator

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY not set in .env")
        sys.exit(1)

    session = LiveSession(api_key)
    image_generator = ImageGenerator(api_key)
    open_audio_file()

    print("=" * 60)
    print("🌙 DREAM WEAVER — End-to-End Test")
    print("=" * 60)

    try:
        print("\n📡 Connecting to Gemini Live API...")

        async def on_ready(live):
            print("✅ Connected!\n")
            # Launch the story script as a background task
            asyncio.create_task(story_script(live))

        # run() keeps the session alive within the async-with context
        await session.run(on_audio, on_tool_call, on_transcript, on_ready=on_ready)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        stats["errors"].append(str(e))

    finally:
        close_audio_file()

    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Audio chunks received:  {stats['audio_chunks']}")
    print(f"  Audio data received:    {stats['audio_bytes'] / 1024:.1f} KB")
    print(f"  Scenes generated:       {stats['scenes_received']}")
    for i, s in enumerate(stats["scenes"]):
        print(f"    Scene {i+1}: \"{s['title']}\" — mood:{s['mood']}, "
              f"elements:{s['element_count']} ({s['new_elements']} new)")
    print(f"  Transcript entries:     {len(stats['transcripts'])}")
    print(f"  Errors:                 {len(stats['errors'])}")

    if os.path.exists("test_output.wav"):
        size_kb = os.path.getsize("test_output.wav") / 1024
        duration_s = stats['audio_bytes'] / (24000 * 2)  # 24kHz, 16-bit
        print(f"  Audio saved to:         test_output.wav ({size_kb:.1f} KB, ~{duration_s:.1f}s)")

    # Evaluate pass/fail
    print("\n" + "─" * 60)
    print("EVALUATION:")
    passed = True

    if stats["audio_chunks"] > 0:
        print(f"  ✅ Audio narration received ({stats['audio_chunks']} chunks, {stats['audio_bytes']/1024:.1f} KB)")
    else:
        print("  ❌ No audio received — voice pipeline broken")
        passed = False

    if stats["scenes_received"] >= 1:
        print(f"  ✅ Scene generation working ({stats['scenes_received']} scenes via function calling)")
    else:
        print("  ❌ No scenes generated — function calling not triggered")
        passed = False

    if len(stats["transcripts"]) > 0:
        narrator_count = sum(1 for t in stats["transcripts"] if t["role"] == "narrator")
        user_count = sum(1 for t in stats["transcripts"] if t["role"] == "user")
        print(f"  ✅ Transcriptions received ({narrator_count} narrator, {user_count} user)")
    else:
        print("  ⚠️  No transcriptions received (may need more time or different config)")

    # Check for element caching
    if stats["scenes_received"] >= 2:
        total_new = sum(s["new_elements"] for s in stats["scenes"])
        total_elements = sum(s["element_count"] for s in stats["scenes"])
        if total_new < total_elements:
            print(f"  ✅ Element reuse detected ({total_elements - total_new}/{total_elements} elements reused)")
        else:
            print(f"  ⚠️  All elements were new across scenes — AI didn't reuse IDs yet")

    if len(stats["errors"]) == 0:
        print("  ✅ No errors")
    else:
        print(f"  ❌ {len(stats['errors'])} errors occurred")
        for err in stats["errors"]:
            print(f"      - {err[:80]}")
        passed = False

    print("─" * 60)
    if passed:
        print("🎉 TEST PASSED — Backend pipeline is working!")
        print("   Audio narration + function calling + scene generation all confirmed.")
        print("   Play test_output.wav to hear the story!")
    else:
        print("💔 TEST FAILED — See issues above")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_story_test())
