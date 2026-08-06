"""Pytest configuration for PuppetStory backend tests."""

import json
from pathlib import Path

import pytest

STORIES_DIR = Path(__file__).parent / "stories"


@pytest.fixture()
def sample_story():
    """Load a sample story from the stories directory."""
    story_file = STORIES_DIR / "dragon_and_the_star.json"
    with open(story_file, "r") as f:
        return json.load(f)
