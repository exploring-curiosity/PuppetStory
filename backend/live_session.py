import asyncio
import json
import traceback
from google import genai
from google.genai import types
from system_prompt import SYSTEM_PROMPT

generate_scene_declaration = {
    "name": "generate_scene",
    "description": (
        "Generate an animated scene illustration for the current story moment. "
        "Call this when introducing new characters, changing settings, dramatic actions, "
        "or when the child adds new story elements."
    ),
    "behavior": "NON_BLOCKING",
    "parameters": {
        "type": "object",
        "properties": {
            "scene_title": {
                "type": "string",
                "description": "Short descriptive title for this scene"
            },
            "mood": {
                "type": "string",
                "enum": ["exciting", "calm", "mysterious", "funny", "magical", "sleepy"],
                "description": "Overall mood affecting visual filters"
            },
            "transition": {
                "type": "string",
                "enum": ["cut", "fade"],
                "description": "How to transition into this scene"
            },
            "elements": {
                "type": "array",
                "description": "List of visual elements in the scene (2-5 elements)",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Persistent unique ID like 'pink_dragon_body', 'cave_background'. Reuse the same ID for recurring elements."
                        },
                        "description": {
                            "type": "string",
                            "description": "Visual description for image generation. Required when is_new is true. Include art style and 'isolated on white background'."
                        },
                        "is_new": {
                            "type": "boolean",
                            "description": "True if this element needs new image generation. False to reuse cached image."
                        },
                        "position_x": {
                            "type": "number",
                            "description": "Horizontal position 0-100 (0=left, 50=center, 100=right)"
                        },
                        "position_y": {
                            "type": "number",
                            "description": "Vertical position 0-100 (0=top, 50=center, 100=bottom)"
                        },
                        "scale": {
                            "type": "number",
                            "description": "Size multiplier. 1.0=normal, 0.5=half, 2.0=double. Default 1.0"
                        },
                        "z_index": {
                            "type": "integer",
                            "description": "Layer order. 0=background (furthest back), higher=closer to viewer"
                        },
                        "animation": {
                            "type": "object",
                            "description": "Animation configuration for this element",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": [
                                        "idle_bob", "oscillate_y", "oscillate_x",
                                        "pulse_scale", "translate_x", "translate_y",
                                        "rotate_oscillate", "float", "fade_in",
                                        "fade_out", "shake", "spin", "twinkle", "none"
                                    ],
                                    "description": "Animation type from the vocabulary"
                                },
                                "speed": {
                                    "type": "string",
                                    "enum": ["slow", "medium", "fast"],
                                    "description": "Animation speed"
                                },
                                "intensity": {
                                    "type": "number",
                                    "description": "Animation intensity from 0.1 to 1.0"
                                }
                            },
                            "required": ["type", "speed"]
                        }
                    },
                    "required": ["id", "is_new", "position_x", "position_y", "z_index", "animation"]
                }
            }
        },
        "required": ["scene_title", "mood", "transition", "elements"]
    }
}

LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"


def get_live_config():
    """Return the Live API session configuration."""
    return {
        "response_modalities": ["AUDIO"],
        "system_instruction": SYSTEM_PROMPT,
        "tools": [{"function_declarations": [generate_scene_declaration]}],
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {"voice_name": "Aoede"}
            }
        },
        "output_audio_transcription": {},
        "input_audio_transcription": {},
    }


class LiveSession:
    """Manages a persistent Gemini Live API session for voice storytelling.
    
    Usage (context-manager style for proper lifecycle):
        session = LiveSession(api_key)
        async with session.connect() as s:
            # s is the raw genai session object
            await s.send_client_content(...)
            async for response in s.receive():
                ...
    
    Usage (server-style with run()):
        session = LiveSession(api_key)
        await session.run(on_audio, on_tool_call, on_transcript, on_ready)
    """

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.session = None
        self._running = False
        self._send_queue = asyncio.Queue()

    def connect(self):
        """Return the async context manager for the Live API session."""
        return self.client.aio.live.connect(
            model=LIVE_MODEL,
            config=get_live_config()
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

            # Run receive loop and send queue processor concurrently
            try:
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self._receive_loop(on_audio, on_tool_call, on_transcript, on_narration_text, on_turn_complete))
                    tg.create_task(self._send_loop())
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
        """Queue a text message to send to the session."""
        await self._send_queue.put(("text", text))

    async def send_tool_response(self, function_call_id: str, function_name: str, result: dict):
        """Queue a function response to send back to the session."""
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

    async def _receive_loop(self, on_audio, on_tool_call, on_transcript, on_narration_text=None, on_turn_complete=None):
        """Main receive loop dispatching to callbacks."""
        while self._running:
            try:
                turn = self.session.receive()
                async for response in turn:
                    # Use response.data as the single source for audio
                    # (it's a convenience accessor for server_content.model_turn.parts inline_data)
                    if response.data:
                        await on_audio(response.data)

                    # Function / tool calls
                    if response.tool_call:
                        await on_tool_call(response.tool_call)

                    # Server content (transcriptions, text parts, turn completion)
                    if response.server_content:
                        sc = response.server_content

                        # Model turn parts — text only (audio already handled via response.data above)
                        if sc.model_turn and sc.model_turn.parts:
                            for part in sc.model_turn.parts:
                                if part.text and on_narration_text:
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
