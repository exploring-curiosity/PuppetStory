import asyncio
import json
import os
import traceback

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from live_session import LiveSession
from image_generator import ImageGenerator

# Load .env from parent directory (PuppetStory/.env)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(title="Dream Weaver Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "dream-weaver"}


@app.websocket("/ws/story")
async def story_websocket(ws: WebSocket):
    await ws.accept()
    print("[Server] WebSocket client connected")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        await ws.send_json({"type": "error", "message": "GOOGLE_API_KEY not set"})
        await ws.close()
        return

    fast_mode = os.getenv("FAST_MODE", "").lower() in ("1", "true", "yes")

    live_session = LiveSession(api_key)
    image_generator = ImageGenerator(api_key, fast_mode=fast_mode)

    # --- Callback definitions ---

    async def on_audio(data: bytes):
        """Forward audio bytes from Gemini to the browser."""
        try:
            await ws.send_bytes(data)
        except Exception:
            pass

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
                        scene_data = dict(fc.args)

                    print(f"[Server] generate_scene: {scene_data.get('scene_title', 'untitled')}")
                    print(f"[Server]   mood={scene_data.get('mood')}, elements={len(scene_data.get('elements', []))}")

                    scene_with_images = await image_generator.process_scene(scene_data)

                    await ws.send_json({
                        "type": "scene",
                        "data": scene_with_images
                    })

                    await live_session.send_tool_response(
                        function_call_id=fc.id,
                        function_name=fc.name,
                        result={"result": "Scene displayed successfully"}
                    )

                except Exception as e:
                    print(f"[Server] Error processing scene: {e}")
                    traceback.print_exc()
                    await live_session.send_tool_response(
                        function_call_id=fc.id,
                        function_name=fc.name,
                        result={"result": "Scene generation failed, continue narrating"}
                    )

    async def on_transcript(text: str, role: str):
        """Forward transcription text to the browser."""
        try:
            await ws.send_json({
                "type": "transcript",
                "role": role,
                "text": text
            })
        except Exception:
            pass

    async def on_narration_text(text: str):
        """Forward narration text to the browser (for display when Gemini returns text instead of audio)."""
        try:
            await ws.send_json({
                "type": "narration_text",
                "text": text
            })
        except Exception:
            pass

    async def on_turn_complete():
        """Notify the browser that the AI finished its turn."""
        try:
            await ws.send_json({"type": "turn_complete"})
        except Exception:
            pass

    async def on_ready(live):
        """Called when Gemini session is connected — start reading browser messages."""
        print("[Server] Gemini session connected, listening for browser messages")
        asyncio.create_task(browser_message_loop(live))

    async def browser_message_loop(live):
        """Read messages from the browser WebSocket and forward to Gemini."""
        try:
            while True:
                message = await ws.receive()

                if message["type"] == "websocket.receive":
                    if "bytes" in message and message["bytes"]:
                        await live.send_audio(message["bytes"])

                    elif "text" in message and message["text"]:
                        try:
                            data = json.loads(message["text"])
                            msg_type = data.get("type")

                            if msg_type == "wind_down":
                                print("[Server] Sleepy time signal received")
                                await live.send_text(
                                    "[PARENT SIGNAL: sleepy time] — Please begin winding down the story. "
                                    "Slow your pace, use calming imagery, and bring the adventure to a "
                                    "peaceful, cozy conclusion."
                                )
                            elif msg_type == "user_text":
                                text = data.get("text", "")
                                print(f"[Server] User text: {text[:80]}")
                                await live.send_text(text)
                            else:
                                print(f"[Server] Unknown message type: {msg_type}")

                        except json.JSONDecodeError:
                            print("[Server] Invalid JSON from client")

                elif message["type"] == "websocket.disconnect":
                    break
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"[Server] Browser message loop error: {e}")
        finally:
            await live.stop()

    try:
        await live_session.run(on_audio, on_tool_call, on_transcript, on_ready=on_ready, on_narration_text=on_narration_text, on_turn_complete=on_turn_complete)
    except Exception as e:
        print(f"[Server] Error: {e}")
        traceback.print_exc()
    finally:
        print("[Server] Session cleaned up")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
