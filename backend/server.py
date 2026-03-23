import asyncio
import json
import os
import re
import time
import traceback

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from live_session import LiveSession
from story_loader import list_stories, load_story
from asset_pipeline import AssetPipeline
from puppet_inference import infer_puppet_commands

# Load .env from parent directory (PuppetStory/.env)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(title="PuppetStory Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FAST_MODE = os.getenv("FAST_MODE", "").lower() in ("1", "true", "yes")


# ─── REST endpoints ─────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "puppet-story"}


@app.get("/api/stories")
async def get_stories():
    """Return catalog of all available stories."""
    return list_stories()


@app.get("/api/stories/{story_id}")
async def get_story(story_id: str):
    """Return full story data including characters, backgrounds, beats."""
    story = load_story(story_id)
    if story is None:
        return {"error": "Story not found"}, 404
    return story


@app.get("/api/stories/{story_id}/assets")
async def get_story_assets(story_id: str):
    """Return all cached asset data URIs for a story."""
    api_key = os.getenv("GOOGLE_API_KEY", "")
    story = load_story(story_id)
    if story is None:
        return {"error": "Story not found"}, 404
    pipeline = AssetPipeline(api_key, fast_mode=FAST_MODE)
    assets = pipeline.get_all_assets(story_id, story)
    return {"story_id": story_id, "assets": assets, "count": len(assets)}


@app.post("/api/stories/{story_id}/generate-assets")
async def generate_story_assets(story_id: str):
    """Generate all images for a story. Returns Server-Sent Events with progress."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return {"error": "GOOGLE_API_KEY not set"}, 500

    story = load_story(story_id)
    if story is None:
        return {"error": "Story not found"}, 404

    pipeline = AssetPipeline(api_key, fast_mode=FAST_MODE)

    async def event_stream():
        async for event in pipeline.generate_story_assets(story):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ─── WebSocket story session ────────────────────────────────────────────

@app.websocket("/ws/story")
async def story_websocket(ws: WebSocket):
    await ws.accept()
    print("[Server] WebSocket client connected")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        await ws.send_json({"type": "error", "message": "GOOGLE_API_KEY not set"})
        await ws.close()
        return

    # Wait for init message with story_id
    story = None
    assets = {}
    try:
        init_raw = await asyncio.wait_for(ws.receive_text(), timeout=10)
        init_msg = json.loads(init_raw)
        if init_msg.get("type") == "init" and init_msg.get("story_id"):
            story = load_story(init_msg["story_id"])
            if story:
                pipeline = AssetPipeline(api_key, fast_mode=FAST_MODE)
                assets = pipeline.get_all_assets(story["id"], story)
                print(f"[Server] Story loaded: {story['title']} ({len(assets)} assets)")
            else:
                print(f"[Server] Story not found: {init_msg['story_id']}")
        else:
            print("[Server] No init message with story_id, proceeding without story context")
    except Exception as e:
        print(f"[Server] Init phase error: {e}, proceeding without story context")

    # Pre-build character scale lookup for O(1) access during tool calls
    char_scales = {}
    if story:
        char_scales = {c["id"]: c.get("scale_factor", 1.0) for c in story.get("characters", [])}

    live_session = LiveSession(api_key, story=story, assets=assets)
    session_t0 = time.monotonic()

    def _ts() -> str:
        """Session-relative timestamp for benchmarking."""
        return f"{time.monotonic() - session_t0:.3f}s"

    # --- Callback definitions ---

    async def on_audio(data: bytes):
        try:
            await ws.send_bytes(data)
        except Exception:
            pass

    async def on_tool_call(tool_call):
        """Handle tool calls with ZERO blocking — send to frontend and respond to Gemini concurrently.
        Key optimization: we fire the tool response IMMEDIATELY so Gemini keeps narrating
        while the frontend processes the scene/animation."""
        t0 = time.monotonic()
        tasks = []

        for fc in tool_call.function_calls:
            try:
                args = fc.args if isinstance(fc.args, dict) else json.loads(fc.args) if isinstance(fc.args, str) else dict(fc.args)

                if fc.name == "set_scene":
                    bg_id = args.get("background_id", "")
                    mood = args.get("mood", "calm")
                    transition = args.get("transition", "crossfade")
                    puppets = args.get("puppets", [])

                    # Attach asset data URIs + apply scale (O(1) lookups)
                    for p in puppets:
                        cid = p.get("character_id", "")
                        if cid in assets:
                            p["image"] = assets[cid]
                        if cid in char_scales:
                            p["scale"] = p.get("scale", 1.0) * char_scales[cid]

                    scene_data = {
                        "background_id": bg_id,
                        "background_image": assets.get(bg_id, ""),
                        "mood": mood,
                        "transition": transition,
                        "puppets": puppets,
                    }
                    _state["current_scene"] = scene_data  # track for puppet inference context

                    # Fire both concurrently: send to frontend + respond to Gemini
                    print(f"[{_ts()}] set_scene: bg={bg_id}, mood={mood}, puppets={len(puppets)}")
                    tasks.append(ws.send_json({"type": "set_scene", "data": scene_data}))
                    tasks.append(live_session.send_tool_response(fc.id, fc.name, {"result": "Scene set successfully"}))

                elif fc.name == "action_sequence":
                    duration = args.get("duration", 3.0)
                    animations = args.get("animations", [])

                    # Convert array format from Gemini → map format for frontend
                    puppets_kf = {}
                    for anim in animations:
                        cid = anim.get("character_id", "")
                        keyframes = anim.get("keyframes", [])
                        easing = anim.get("easing", "ease-in-out")

                        # Apply character scale factor to keyframes
                        base_scale = char_scales.get(cid, 1.0)
                        if base_scale != 1.0:
                            for kf in keyframes:
                                if "scale" in kf:
                                    kf["scale"] = kf["scale"] * base_scale

                        puppets_kf[cid] = {"keyframes": keyframes, "easing": easing}

                    action_data = {"duration": duration, "puppets": puppets_kf}
                    print(f"[{_ts()}] action_sequence: duration={duration}s, puppets={list(puppets_kf.keys())}")
                    tasks.append(ws.send_json({"type": "action_sequence", "data": action_data}))
                    tasks.append(live_session.send_tool_response(fc.id, fc.name, {"result": "Animation played"}))

                else:
                    print(f"[{_ts()}] Unknown tool call: {fc.name}")
                    tasks.append(live_session.send_tool_response(fc.id, fc.name, {"result": "Unknown function"}))

            except Exception as e:
                print(f"[{_ts()}] Error handling tool {fc.name}: {e}")
                traceback.print_exc()
                tasks.append(live_session.send_tool_response(fc.id, fc.name, {"result": f"Error: {str(e)[:100]}"}))

        # Execute ALL sends concurrently — no serial waiting
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        elapsed_ms = (time.monotonic() - t0) * 1000
        print(f"[{_ts()}] Tool call batch processed in {elapsed_ms:.1f}ms")

    async def on_transcript(text: str, role: str):
        try:
            await ws.send_json({"type": "transcript", "role": role, "text": text})
        except Exception:
            pass

    _narration_buffer = ""  # accumulate narration to detect text-tag tool calls

    async def on_narration_text(text: str):
        nonlocal _narration_buffer
        # Accumulate text and check for text-tag tool calls the model emits
        _narration_buffer += text

        # Check for complete text-tag tool calls
        for tag_name in ("set_scene", "action_sequence"):
            pattern = rf"<{tag_name}\s+([^>]+)>"
            match = re.search(pattern, _narration_buffer)
            if match:
                raw_attrs = match.group(1)
                print(f"[{_ts()}] Intercepted text-tag {tag_name}: {raw_attrs[:80]}")
                _narration_buffer = _narration_buffer[match.end():]
                try:
                    await _dispatch_text_tag_tool(tag_name, raw_attrs)
                except Exception as e:
                    print(f"[{_ts()}] Text-tag parse error for {tag_name}: {e}")
                return  # don't forward tool-call text to frontend

        # Flush buffer if it's getting long and has no partial tag
        if len(_narration_buffer) > 200 and "<" not in _narration_buffer[-50:]:
            _narration_buffer = _narration_buffer[-50:]

        # Forward clean narration text (skip text containing partial tags)
        if not text.strip().startswith("<"):
            try:
                await ws.send_json({"type": "narration_text", "text": text})
            except Exception:
                pass

    async def _dispatch_text_tag_tool(tag_name: str, raw_attrs: str):
        """Parse text-tag attributes and dispatch as a real tool call to the frontend."""
        import html
        raw_attrs = html.unescape(raw_attrs)

        if tag_name == "set_scene":
            # Extract background_id, mood, puppets
            bg_match = re.search(r'background_id="([^"]+)"', raw_attrs)
            mood_match = re.search(r'mood="([^"]+)"', raw_attrs)
            bg_id = bg_match.group(1) if bg_match else "meadow"
            mood = mood_match.group(1) if mood_match else "cheerful"

            # Try to parse puppets array
            puppets = []
            puppets_match = re.search(r'puppets="?(\[.+?\])"?', raw_attrs)
            if puppets_match:
                try:
                    puppets = json.loads(puppets_match.group(1))
                except json.JSONDecodeError:
                    pass

            scene_data = {
                "background_id": bg_id,
                "mood": mood,
                "transition": "crossfade",
                "puppets": puppets
            }
            print(f"[{_ts()}] text-tag set_scene: bg={bg_id}, mood={mood}, puppets={len(puppets)}")
            await ws.send_json({"type": "set_scene", "data": scene_data})

        elif tag_name == "action_sequence":
            dur_match = re.search(r'duration="([^"]+)"', raw_attrs)
            duration = float(dur_match.group(1)) if dur_match else 2.0

            # Try to parse animations
            puppets_kf = {}
            anims_match = re.search(r'animations="?(\[.+?\])"?', raw_attrs)
            if anims_match:
                try:
                    anims = json.loads(anims_match.group(1))
                    for anim in anims:
                        cid = anim.get("character_id", "")
                        kfs = anim.get("keyframes", [])
                        easing = anim.get("easing", "easeInOut")
                        if cid:
                            puppets_kf[cid] = {"keyframes": kfs, "easing": easing}
                except json.JSONDecodeError:
                    pass

            action_data = {"duration": duration, "puppets": puppets_kf}
            print(f"[{_ts()}] text-tag action_sequence: dur={duration}s, puppets={list(puppets_kf.keys())}")
            await ws.send_json({"type": "action_sequence", "data": action_data})

    _live_ref = None  # will be set in on_ready
    _last_auto_continue_t = 0.0
    _pending_child_text = None  # tracks last child interruption needing tool calls
    _child_tool_nudge_sent = False  # True once we've nudged for this child input

    async def on_turn_complete():
        nonlocal _last_auto_continue_t, _pending_child_text, _child_tool_nudge_sent
        try:
            await ws.send_json({"type": "turn_complete"})
        except Exception:
            pass

        now = time.time()
        if _live_ref is None or (now - _last_auto_continue_t) <= 5.0:
            return

        _last_auto_continue_t = now

        # If there's a pending child interruption that hasn't gotten a tool-call nudge yet,
        # send a specific request to update the puppet stage for the child's input.
        if _pending_child_text and not _child_tool_nudge_sent:
            _child_tool_nudge_sent = True
            child_req = _pending_child_text[:80]
            print(f"[{_ts()}] Tool-call nudge for child input: {child_req}")
            await _live_ref.send_text(
                f'Now update the puppet stage for the child\'s request: "{child_req}". '
                f'Call set_scene to set the right background/mood/character positions, '
                f'and call action_sequence to animate the characters. Then continue narrating.'
            )
        else:
            print(f"[{_ts()}] Auto-continue after TURN_COMPLETE")
            await _live_ref.send_text("Continue. Next beat — call set_scene and action_sequence. Keep narrating!")

    async def on_ready(live):
        nonlocal _live_ref
        _live_ref = live
        print(f"[{_ts()}] Gemini session connected, sending kickstart prompt")
        # send_text (turn_complete=True) for kickstart — reliable 4-8s TTFAB
        story_title = story["title"] if story else "a story"
        await live.send_text(
            f'Begin "{story_title}" now. Call set_scene first, then greet the child. Go!'
        )
        asyncio.create_task(browser_message_loop(live))

    _state = {"current_scene": None}  # mutable container for cross-closure state

    async def _puppet_inference_task(child_text: str):
        """Run puppet inference in parallel with the audio model's narration.
        Generates set_scene/action_sequence commands server-side and dispatches
        them directly to the frontend."""
        try:
            result = await infer_puppet_commands(child_text, story, _state["current_scene"])
            if not result:
                return

            # Dispatch set_scene if needed
            if result.get("needs_scene_change") and result.get("set_scene"):
                sc = result["set_scene"]
                scene_data = {
                    "background_id": sc.get("background_id", "meadow"),
                    "mood": sc.get("mood", "cheerful"),
                    "transition": "crossfade",
                    "puppets": sc.get("puppets", []),
                }
                _state["current_scene"] = scene_data
                print(f"[{_ts()}] PuppetInference set_scene: bg={scene_data['background_id']}, mood={scene_data['mood']}")
                await ws.send_json({"type": "set_scene", "data": scene_data})

            # Dispatch action_sequence
            if result.get("action_sequence"):
                aseq = result["action_sequence"]
                duration = aseq.get("duration", 3.0)
                puppets_kf = {}
                for anim in aseq.get("animations", []):
                    cid = anim.get("character_id", "")
                    kfs = anim.get("keyframes", [])
                    easing = anim.get("easing", "easeInOut")
                    if cid:
                        puppets_kf[cid] = {"keyframes": kfs, "easing": easing}
                if puppets_kf:
                    action_data = {"duration": duration, "puppets": puppets_kf}
                    print(f"[{_ts()}] PuppetInference action_sequence: dur={duration}s, puppets={list(puppets_kf.keys())}")
                    await ws.send_json({"type": "action_sequence", "data": action_data})

        except Exception as e:
            print(f"[{_ts()}] PuppetInference task error: {e}")

    async def browser_message_loop(live):
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
                                print(f"[{_ts()}] Sleepy time signal received")
                                await live.send_realtime_text(
                                    "[PARENT SIGNAL: sleepy time] — Begin winding down. "
                                    "Slow your pace, use calming imagery, bring the story to a peaceful conclusion."
                                )
                            elif msg_type == "user_text":
                                text = data.get("text", "")
                                print(f"[{_ts()}] User text: {text[:80]}")
                                _pending_child_text = text
                                _child_tool_nudge_sent = False
                                # Send instant acknowledgment to frontend
                                await ws.send_json({
                                    "type": "thinking",
                                    "text": text[:50],
                                })
                                # Send child text to audio model for narration
                                await live.send_realtime_text(text)
                                # Fire parallel puppet inference to generate
                                # set_scene + action_sequence server-side
                                asyncio.create_task(
                                    _puppet_inference_task(text)
                                )
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
        await live_session.run(
            on_audio, on_tool_call, on_transcript,
            on_ready=on_ready, on_narration_text=on_narration_text,
            on_turn_complete=on_turn_complete
        )
    except Exception as e:
        print(f"[Server] Error: {e}")
        traceback.print_exc()
    finally:
        print("[Server] Session cleaned up")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
