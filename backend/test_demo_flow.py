"""
Full multi-step demo flow test.
Simulates parent/child sending text prompts, verifies narration + scenes + images.
"""
import asyncio
import json
import time
import websockets

SCRIPT = [
    ("Hello Dream Weaver! My child wants a bedtime story tonight.", 12),
    ("I want a story about a PINK DRAGON that lives on a snowy mountain!", 18),
    ("The dragon should blow RAINBOW BUBBLES instead of fire! And the bubbles make flowers grow!", 18),
    ("Can a little bunny come ride on the dragon?", 18),
]


async def test():
    uri = "ws://localhost:8000/ws/story"
    print(f"Connecting to {uri}...")

    async with websockets.connect(uri) as ws:
        audio_count = 0
        text_parts = []
        scenes = []

        async def recv_until(secs):
            nonlocal audio_count
            end = time.time() + secs
            while time.time() < end:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    if isinstance(msg, bytes):
                        audio_count += 1
                    else:
                        data = json.loads(msg)
                        t = data.get("type")
                        if t == "narration_text":
                            text_parts.append(data["text"])
                        elif t == "scene":
                            d = data["data"]
                            els = d.get("elements", [])
                            has_real = any(
                                "data:image/" in str(e.get("image", ""))[:20]
                                for e in els
                            )
                            info = (
                                f'"{d.get("scene_title")}" '
                                f'mood={d.get("mood")} '
                                f"els={len(els)} real_img={has_real}"
                            )
                            scenes.append(info)
                            print(f"  SCENE: {info}")
                            for e in els:
                                img_preview = str(e.get("image", ""))[:50]
                                anim = e.get("animation", {}).get("type", "?")
                                print(f"    [{e['id']}] anim={anim} img={img_preview}...")
                except asyncio.TimeoutError:
                    continue

        for i, (text, wait) in enumerate(SCRIPT):
            print(f"\n--- Step {i+1}: {text[:70]} ---")
            await ws.send(json.dumps({"type": "user_text", "text": text}))
            await recv_until(wait)
            print(
                f"  Running totals: audio={audio_count} "
                f"text_chunks={len(text_parts)} scenes={len(scenes)}"
            )

        print("\n" + "=" * 50)
        print("FINAL SUMMARY")
        print("=" * 50)
        print(f"  Audio chunks:          {audio_count}")
        print(f"  Narration text chunks: {len(text_parts)}")
        print(f"  Scenes generated:      {len(scenes)}")
        for i, s in enumerate(scenes):
            print(f"    Scene {i+1}: {s}")
        narration = "".join(text_parts)
        if narration:
            print(f"  Narration preview: {narration[:300]}")
        print()
        if audio_count > 0:
            print("  OK audio narration")
        if len(text_parts) > 0:
            print("  OK text narration (browser TTS will speak this)")
        if len(scenes) > 0:
            print("  OK scene generation + images")
        if audio_count == 0 and len(text_parts) == 0:
            print("  WARN: No narration received")
        if len(scenes) == 0:
            print("  WARN: No scenes generated (model may need more turns)")
        print("\nDONE")


if __name__ == "__main__":
    asyncio.run(test())
