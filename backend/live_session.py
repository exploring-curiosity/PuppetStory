import asyncio
import json
import time
import traceback
from google import genai
from google.genai import types
from system_prompt import build_system_prompt

# ─── Tool declarations ──────────────────────────────────────────────────

set_scene_declaration = {
    "name": "set_scene",
    "description": (
        "Change the scene background and set initial puppet positions. "
        "Call when transitioning between story beats or changing locations. "
        "Use background_id from the story data. Position puppets using x,y coordinates (0-100)."
    ),
    "behavior": "NON_BLOCKING",
    "parameters": {
        "type": "object",
        "properties": {
            "background_id": {
                "type": "string",
                "description": "ID of the background from the story data (e.g. 'meadow', 'brick_house')"
            },
            "mood": {
                "type": "string",
                "enum": ["exciting", "calm", "mysterious", "funny", "magical", "sleepy", "tense", "triumphant"],
                "description": "Overall mood affecting the visual atmosphere"
            },
            "transition": {
                "type": "string",
                "enum": ["crossfade", "cut", "slide_left", "slide_right"],
                "description": "How to transition into this scene"
            },
            "puppets": {
                "type": "array",
                "description": "List of characters to display in this scene with their positions",
                "items": {
                    "type": "object",
                    "properties": {
                        "character_id": {
                            "type": "string",
                            "description": "ID of the character from the story data"
                        },
                        "x": {
                            "type": "number",
                            "description": "Horizontal position 0-100 (0=left, 50=center, 100=right)"
                        },
                        "y": {
                            "type": "number",
                            "description": "Vertical position 0-100 (0=top, 50=middle, 100=bottom)"
                        },
                        "scale": {
                            "type": "number",
                            "description": "Size multiplier relative to character's base scale. 1.0=normal. Default 1.0"
                        },
                        "rotation": {
                            "type": "number",
                            "description": "Rotation in degrees. 0=upright. Positive=clockwise. Default 0"
                        },
                        "opacity": {
                            "type": "number",
                            "description": "Visibility 0.0 (invisible) to 1.0 (fully visible). Default 1.0"
                        }
                    },
                    "required": ["character_id", "x", "y"]
                }
            }
        },
        "required": ["background_id", "mood", "puppets"]
    }
}

action_sequence_declaration = {
    "name": "action_sequence",
    "description": (
        "Animate puppets with timed keyframe sequences. Use for character movement, "
        "interactions, gestures, and dramatic moments. Each puppet gets an array of "
        "keyframes defining position, scale, rotation, and opacity at specific times. "
        "The frontend smoothly interpolates between keyframes. "
        "IMPORTANT: When puppets interact, coordinate their positions so they are adjacent. "
        "Respect relative sizes (e.g. a mouse should be much smaller than a bear)."
    ),
    "behavior": "NON_BLOCKING",
    "parameters": {
        "type": "object",
        "properties": {
            "duration": {
                "type": "number",
                "description": "Total animation duration in seconds (1-10)"
            },
            "animations": {
                "type": "array",
                "description": "List of puppet animations, one per character to animate",
                "items": {
                    "type": "object",
                    "properties": {
                        "character_id": {
                            "type": "string",
                            "description": "ID of the character to animate"
                        },
                        "easing": {
                            "type": "string",
                            "enum": ["linear", "ease-in", "ease-out", "ease-in-out"],
                            "description": "Easing function for interpolation between keyframes"
                        },
                        "keyframes": {
                            "type": "array",
                            "description": "Timed keyframes for this puppet's motion",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "t": {
                                        "type": "number",
                                        "description": "Time in seconds from sequence start"
                                    },
                                    "x": {
                                        "type": "number",
                                        "description": "Horizontal position 0-100"
                                    },
                                    "y": {
                                        "type": "number",
                                        "description": "Vertical position 0-100"
                                    },
                                    "rotation": {
                                        "type": "number",
                                        "description": "Rotation in degrees"
                                    },
                                    "scale": {
                                        "type": "number",
                                        "description": "Size multiplier relative to character base scale"
                                    },
                                    "opacity": {
                                        "type": "number",
                                        "description": "Visibility 0.0-1.0"
                                    }
                                },
                                "required": ["t", "x", "y"]
                            }
                        }
                    },
                    "required": ["character_id", "keyframes"]
                }
            }
        },
        "required": ["duration", "animations"]
    }
}

LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"


def get_live_config(story: dict = None):
    """Return the Live API session configuration."""
    system_prompt = build_system_prompt(story)
    return {
        "response_modalities": ["AUDIO"],
        "system_instruction": system_prompt,
        "tools": [{"function_declarations": [set_scene_declaration, action_sequence_declaration]}],
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {"voice_name": "Aoede"}
            }
        },
        "output_audio_transcription": {},
        "input_audio_transcription": {},
    }


class LiveSession:
    """Manages a persistent Gemini Live API session for interactive puppet storytelling."""

    def __init__(self, api_key: str, story: dict = None, assets: dict = None):
        self.client = genai.Client(api_key=api_key)
        self.story = story
        self.assets = assets or {}
        self.session = None
        self._running = False
        self._send_queue = asyncio.Queue()
        self._watchdog_armed_at = None  # timestamp when child text was sent
        self._last_audio_at = None  # timestamp of last audio received

    def connect(self):
        """Return the async context manager for the Live API session."""
        return self.client.aio.live.connect(
            model=LIVE_MODEL,
            config=get_live_config(self.story)
        )

    async def run(self, on_audio, on_tool_call, on_transcript, on_ready=None, on_narration_text=None, on_turn_complete=None):
        """
        Run the full session lifecycle within the proper async context.
        Call on_ready(session) once connected so callers can send messages.
        Processes the receive loop and dispatches to callbacks.
        Also processes outbound messages from the send queue.
        """
        async with self.connect() as session:
            self.session = session
            self._running = True
            print(f"[LiveSession] Connected to {LIVE_MODEL}")

            if on_ready:
                await on_ready(self)

            # Run receive loop, send queue, and silence watchdog concurrently
            try:
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self._receive_loop(on_audio, on_tool_call, on_transcript, on_narration_text, on_turn_complete))
                    tg.create_task(self._send_loop())
                    tg.create_task(self._silence_watchdog())
            except* asyncio.CancelledError:
                pass
            except* Exception as eg:
                for e in eg.exceptions:
                    if "1000" not in str(e):
                        print(f"[LiveSession] Error: {e}")

        self.session = None
        self._running = False
        print("[LiveSession] Disconnected")

    async def send_audio(self, pcm_bytes: bytes):
        """Queue raw PCM audio bytes to send to Gemini."""
        await self._send_queue.put(("audio", pcm_bytes))

    async def send_text(self, text: str):
        """Queue a text message as a full turn (triggers thinking). Use for kickstart only."""
        await self._send_queue.put(("text", text))

    async def send_realtime_text(self, text: str):
        """Send child text via realtime input — non-interrupting, model processes incrementally.
        Also arms the silence watchdog to re-prompt if model goes silent."""
        if self.session:
            try:
                await self.session.send_realtime_input(text=text)
                # Arm watchdog: if no audio within 12s, send a nudge
                self._watchdog_armed_at = time.time()
                return
            except Exception as e:
                print(f"[LiveSession] Realtime text failed, falling back to queued: {e}")
        await self._send_queue.put(("text", text))

    async def send_tool_response(self, function_call_id: str, function_name: str, result: dict):
        """Send tool response DIRECTLY to the session for minimum latency.
        Falls back to queue if direct send fails."""
        if self.session:
            try:
                response = types.FunctionResponse(
                    id=function_call_id,
                    name=function_name,
                    response={**result, "scheduling": "SILENT"}
                )
                await self.session.send_tool_response(
                    function_responses=[response]
                )
                return
            except Exception as e:
                print(f"[LiveSession] Direct tool response failed, queuing: {e}")
        # Fallback to queue
        await self._send_queue.put(("tool_response", (function_call_id, function_name, result)))

    async def stop(self):
        """Signal the session to stop."""
        self._running = False
        await self._send_queue.put(("stop", None))

    async def _send_loop(self):
        """Process outbound messages from the queue."""
        while self._running:
            try:
                msg_type, payload = await asyncio.wait_for(
                    self._send_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            if msg_type == "stop":
                break

            try:
                if msg_type == "audio":
                    await self.session.send_realtime_input(
                        audio={"data": payload, "mime_type": "audio/pcm;rate=16000"}
                    )
                elif msg_type == "text":
                    await self.session.send_client_content(
                        turns={"role": "user", "parts": [{"text": payload}]},
                        turn_complete=True
                    )
                    # Don't arm watchdog here — it's armed by on_turn_complete in server.py
                    # Arming here caused double-thinking on kickstart (12s watchdog + model thinking)
                elif msg_type == "tool_response":
                    fc_id, fc_name, result = payload
                    response = types.FunctionResponse(
                        id=fc_id,
                        name=fc_name,
                        response={**result, "scheduling": "SILENT"}
                    )
                    await self.session.send_tool_response(
                        function_responses=[response]
                    )
            except Exception as e:
                if self._running:
                    print(f"[LiveSession] Send error: {e}")

    async def _silence_watchdog(self):
        """Monitor for prolonged silence after TURN_COMPLETE or child text.
        Sends up to 2 nudges via send_client_content (turn_complete=True).
        Re-arms after first nudge to catch dead thinking cycles."""
        WATCHDOG_TIMEOUT = 10  # seconds
        _nudge_count = 0
        MAX_NUDGES = 2
        while self._running:
            await asyncio.sleep(3)
            if self._watchdog_armed_at is not None:
                elapsed = time.time() - self._watchdog_armed_at
                if elapsed >= WATCHDOG_TIMEOUT:
                    _nudge_count += 1
                    print(f"[LiveSession] Silence watchdog triggered ({elapsed:.1f}s, nudge #{_nudge_count}) — sending nudge")
                    if _nudge_count >= MAX_NUDGES:
                        self._watchdog_armed_at = None
                        _nudge_count = 0
                    else:
                        # Re-arm for a second attempt
                        self._watchdog_armed_at = time.time()
                    try:
                        await self.session.send_client_content(
                            turns={"role": "user", "parts": [{"text": "Continue. Next beat now."}]},
                            turn_complete=True
                        )
                    except Exception as e:
                        print(f"[LiveSession] Watchdog nudge failed: {e}")
            else:
                _nudge_count = 0  # reset when not armed

    async def _receive_loop(self, on_audio, on_tool_call, on_transcript, on_narration_text=None, on_turn_complete=None):
        """Main receive loop dispatching to callbacks."""
        while self._running:
            try:
                turn = self.session.receive()
                async for response in turn:
                    # Use response.data as the single source for audio
                    # (it's a convenience accessor for server_content.model_turn.parts inline_data)
                    if response.data:
                        self._last_audio_at = time.time()
                        self._watchdog_armed_at = None  # disarm watchdog on audio
                        await on_audio(response.data)

                    # Function / tool calls
                    if response.tool_call:
                        await on_tool_call(response.tool_call)

                    # Server content (transcriptions, text parts, turn completion)
                    if response.server_content:
                        sc = response.server_content

                        # Model turn parts — text only (audio already handled via response.data above)
                        # Filter out reasoning/thinking text and control tokens
                        if sc.model_turn and sc.model_turn.parts:
                            for part in sc.model_turn.parts:
                                if part.text and on_narration_text:
                                    txt = part.text.strip()
                                    # Skip thinking tokens, code blocks, and reasoning headers
                                    if not txt or txt.startswith("<ctrl") or txt.startswith("```"):
                                        continue
                                    # Filter model reasoning text (e.g. "**Initiating story start**\n\nI'm setting...")
                                    if txt.startswith("**") and ("\n" in txt or len(txt) > 80):
                                        continue
                                    await on_narration_text(part.text)

                        # Output transcription (narrator)
                        if hasattr(sc, 'output_transcription') and sc.output_transcription:
                            if hasattr(sc.output_transcription, 'text') and sc.output_transcription.text:
                                await on_transcript(sc.output_transcription.text, "narrator")

                        # Input transcription (user)
                        if hasattr(sc, 'input_transcription') and sc.input_transcription:
                            if hasattr(sc.input_transcription, 'text') and sc.input_transcription.text:
                                await on_transcript(sc.input_transcription.text, "user")

                        # Turn complete signal
                        if sc.turn_complete and on_turn_complete:
                            await on_turn_complete()

            except asyncio.CancelledError:
                break
            except Exception as e:
                error_str = str(e)
                # Normal close or server-side disconnect — stop cleanly
                if any(code in error_str for code in ["1000", "1011", "1006", "ConnectionClosed"]):
                    reason = "normally" if "1000" in error_str else f"(server error: {error_str[:80]})"
                    print(f"[LiveSession] Session ended {reason}")
                    self._running = False
                    break
                if self._running:
                    print(f"[LiveSession] Receive error: {e}")
                    traceback.print_exc()
                    self._running = False
                    break
