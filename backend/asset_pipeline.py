"""
Asset pipeline — pre-generates all character and background images for a story
using Nano Banana 2 (gemini-3.1-flash-image-preview) with disk caching.
"""

import asyncio
import base64
import hashlib
import io
import os
import time
from pathlib import Path
from typing import AsyncGenerator, Optional

from google import genai
from google.genai import types

CACHE_DIR = Path(__file__).parent / "asset_cache"
IMAGE_MODEL = "gemini-3.1-flash-image-preview"

# Concurrency limit for parallel image generation
MAX_CONCURRENT = 4


class AssetPipeline:
    def __init__(self, api_key: str, fast_mode: bool = False):
        self.client = genai.Client(api_key=api_key)
        self.fast_mode = fast_mode

    def get_story_cache_dir(self, story_id: str) -> Path:
        d = CACHE_DIR / story_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def is_cached(self, story_id: str, element_id: str) -> bool:
        cache_dir = self.get_story_cache_dir(story_id)
        return any((cache_dir / f"{element_id}{ext}").exists() for ext in (".svg", ".png", ".jpg"))

    def get_cached_path(self, story_id: str, element_id: str) -> Optional[Path]:
        cache_dir = self.get_story_cache_dir(story_id)
        for ext in (".svg", ".png", ".jpg"):
            p = cache_dir / f"{element_id}{ext}"
            if p.exists():
                return p
        return None

    def get_cached_data_uri(self, story_id: str, element_id: str) -> Optional[str]:
        path = self.get_cached_path(story_id, element_id)
        if path is None:
            return None
        mime_map = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg"}
        mime = mime_map.get(path.suffix, "image/png")
        b64 = base64.b64encode(path.read_bytes()).decode()
        return f"data:{mime};base64,{b64}"

    async def generate_story_assets(self, story: dict) -> AsyncGenerator[dict, None]:
        """
        Generate all images for a story. Yields progress events:
          {"event": "start", "total": N}
          {"event": "progress", "done": M, "total": N, "current": "element_id", "type": "character|background|cover"}
          {"event": "cached", "done": M, "total": N, "current": "element_id"}
          {"event": "error", "element": "element_id", "message": "..."}
          {"event": "complete", "total": N, "duration_s": T}
        """
        story_id = story["id"]
        tasks = []

        # Cover image
        if story.get("cover_prompt"):
            tasks.append({
                "element_id": f"_cover",
                "prompt": story["cover_prompt"],
                "type": "cover",
                "format": "jpg",
            })

        # Character images (PNG for transparency)
        for char in story.get("characters", []):
            tasks.append({
                "element_id": char["id"],
                "prompt": char.get("visual_prompt", char.get("description", "")),
                "type": "character",
                "format": "png",
            })

        # Background images (JPG)
        for bg in story.get("backgrounds", []):
            tasks.append({
                "element_id": bg["id"],
                "prompt": bg.get("visual_prompt", bg.get("description", "")),
                "type": "background",
                "format": "jpg",
            })

        total = len(tasks)
        yield {"event": "start", "total": total}

        done = 0
        start_time = time.time()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def gen_one(task: dict) -> dict:
            nonlocal done
            eid = task["element_id"]
            if self.is_cached(story_id, eid):
                done += 1
                return {"event": "cached", "done": done, "total": total, "current": eid}

            async with semaphore:
                try:
                    if self.fast_mode:
                        await self._generate_placeholder(story_id, eid, task["prompt"], task["format"])
                    else:
                        await self._generate_image(story_id, eid, task["prompt"], task["format"])
                    done += 1
                    return {"event": "progress", "done": done, "total": total, "current": eid, "type": task["type"]}
                except Exception as e:
                    done += 1
                    print(f"[AssetPipeline] Error generating {eid}: {e}")
                    return {"event": "error", "element": eid, "message": str(e)[:200], "done": done, "total": total}

        # Run with bounded concurrency, yield results as they complete
        pending = [asyncio.create_task(gen_one(t)) for t in tasks]
        for coro in asyncio.as_completed(pending):
            result = await coro
            yield result

        duration = time.time() - start_time
        yield {"event": "complete", "total": total, "duration_s": round(duration, 1)}

    async def _generate_image(self, story_id: str, element_id: str, prompt: str, fmt: str):
        """Generate a single image using Nano Banana 2."""
        cache_dir = self.get_story_cache_dir(story_id)

        response = self.client.models.generate_content(
            model=IMAGE_MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                img_bytes = part.inline_data.data
                ext = "png" if fmt == "png" else "jpg"
                out_path = cache_dir / f"{element_id}.{ext}"
                out_path.write_bytes(img_bytes)
                print(f"[AssetPipeline] Generated {element_id}.{ext} ({len(img_bytes)} bytes)")
                return

        raise RuntimeError(f"No image data in response for {element_id}")

    async def _generate_placeholder(self, story_id: str, element_id: str, prompt: str, fmt: str):
        """Generate a colored placeholder (fast mode, no API calls)."""
        from image_generator import _svg_puppet, _svg_background, _clean_svg
        cache_dir = self.get_story_cache_dir(story_id)

        is_bg = fmt == "jpg"
        if is_bg:
            svg = _clean_svg(_svg_background(element_id, prompt))
        else:
            svg = _clean_svg(_svg_puppet(element_id, prompt))

        out_path = cache_dir / f"{element_id}.svg"
        out_path.write_text(svg)
        print(f"[AssetPipeline] Fast placeholder: {element_id}")

    def get_all_assets(self, story_id: str, story: dict) -> dict:
        """Return a map of element_id -> data URI for all cached assets."""
        assets = {}

        # Cover
        uri = self.get_cached_data_uri(story_id, "_cover")
        if uri:
            assets["_cover"] = uri

        # Characters
        for char in story.get("characters", []):
            uri = self.get_cached_data_uri(story_id, char["id"])
            if uri:
                assets[char["id"]] = uri

        # Backgrounds
        for bg in story.get("backgrounds", []):
            uri = self.get_cached_data_uri(story_id, bg["id"])
            if uri:
                assets[bg["id"]] = uri

        return assets
