"""Unit tests for story_loader — no API keys or network access required."""

from pathlib import Path
import json
import tempfile
import story_loader

STORIES_DIR = Path(story_loader.__file__).parent / "stories"


def test_list_stories_returns_all_catalogs():
    catalog = story_loader.list_stories()
    assert len(catalog) == 4
    assert all("id" in s and "title" in s and "beat_count" in s for s in catalog)


def test_load_story_returns_full_story():
    story = story_loader.load_story("dragon_and_the_star")
    assert story is not None
    assert len(story["characters"]) > 0
    assert len(story["beats"]) > 0
    assert story["id"] == "dragon_and_the_star"


def test_load_story_returns_none_for_missing_id():
    assert story_loader.load_story("nonexistent_story") is None


def test_invalid_story_files_are_skipped():
    with tempfile.TemporaryDirectory() as tmpdir:
        invalid_path = Path(tmpdir) / "bad.json"
        invalid_path.write_text("not valid json")
        original_dir = story_loader.STORIES_DIR
        try:
            story_loader.STORIES_DIR = Path(tmpdir)
            catalog = story_loader.list_stories()
            assert catalog == []
        finally:
            story_loader.STORIES_DIR = original_dir
