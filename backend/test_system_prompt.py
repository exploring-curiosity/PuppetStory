"""Unit tests for system_prompt.build_system_prompt."""

from system_prompt import build_system_prompt


def _make_story():
    return {
        "title": "The Brave Knight",
        "essence": "Courage comes from within",
        "characters": [
            {"id": "knight_1", "name": "Sir Pip", "description": "a tiny brave knight"},
        ],
        "backgrounds": [{"id": "castle", "description": "a grand castle"}],
    }


def test_build_system_prompt_no_story_returns_base():
    result = build_system_prompt()
    assert "## Your Tools" in result
    assert "## CRITICAL RULES" in result


def test_build_system_prompt_includes_story_data():
    result = build_system_prompt(_make_story())
    assert "The Brave Knight" in result
    assert "Courage comes from within" in result
    assert "knight_1" in result
    assert "castle" in result


def test_build_system_prompt_contains_all_critical_rules_sections():
    result = build_system_prompt(_make_story())
    for section in [
        "## CRITICAL RULES",
        "### Immediate Start",
        "### Tool Usage",
        "### Narration Style",
        "### Child Interaction — INSTANT RESPONSE",
        "### Content Safety",
        "### CRITICAL RULES FOR THIS STORY",
    ]:
        assert section in result, f"Missing section: {section}"
