"""
Story loader — reads and validates story JSON files from the stories/ directory.
"""

import json
import os
from pathlib import Path
from typing import Optional

STORIES_DIR = Path(__file__).parent / "stories"


def list_stories() -> list[dict]:
    """Return catalog metadata for all available stories (no full beat data)."""
    catalog = []
    for path in sorted(STORIES_DIR.glob("*.json")):
        try:
            with open(path, "r") as f:
                story = json.load(f)
            catalog.append({
                "id": story["id"],
                "title": story["title"],
                "synopsis": story["synopsis"],
                "cover_prompt": story.get("cover_prompt", ""),
                "age_range": story.get("age_range", [5, 12]),
                "duration_minutes": story.get("duration_minutes", 10),
                "character_count": len(story.get("characters", [])),
                "beat_count": len(story.get("beats", [])),
            })
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[StoryLoader] Skipping invalid story {path.name}: {e}")
    return catalog


def load_story(story_id: str) -> Optional[dict]:
    """Load a full story by ID. Returns None if not found."""
    path = STORIES_DIR / f"{story_id}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            story = json.load(f)
        _validate_story(story)
        return story
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[StoryLoader] Error loading {story_id}: {e}")
        return None


def _validate_story(story: dict):
    """Basic validation of story structure."""
    required_top = ["id", "title", "synopsis", "essence", "characters", "backgrounds", "beats"]
    for key in required_top:
        if key not in story:
            raise ValueError(f"Missing required field: {key}")

    char_ids = {c["id"] for c in story["characters"]}
    bg_ids = {b["id"] for b in story["backgrounds"]}

    for beat in story["beats"]:
        if "id" not in beat:
            raise ValueError(f"Beat missing 'id'")
        if beat.get("scene") and beat["scene"] not in bg_ids:
            raise ValueError(f"Beat '{beat['id']}' references unknown background '{beat['scene']}'")
        for cid in beat.get("characters_present", []):
            if cid not in char_ids:
                raise ValueError(f"Beat '{beat['id']}' references unknown character '{cid}'")

    print(f"[StoryLoader] Validated '{story['title']}': {len(story['characters'])} characters, "
          f"{len(story['backgrounds'])} backgrounds, {len(story['beats'])} beats")
