"""
Server-side puppet inference module.

When a child interrupts the story, the audio model handles narration but often
doesn't call set_scene/action_sequence functions. This module runs a PARALLEL
fast Gemini text API call to infer the correct puppet stage commands from the
child's request + current story context, and returns them for the server to
dispatch directly to the frontend.

This decouples puppet stage updates from the audio model's tool-calling behavior.
"""

import json
import os
import time
from google import genai

# Use Gemini Flash for speed — text-only, no audio overhead
INFERENCE_MODEL = "gemini-2.0-flash-lite"


def _build_inference_prompt(
    child_text: str,
    story: dict,
    current_scene: dict | None = None,
) -> str:
    """Build a prompt for the text model to generate puppet commands."""

    # Collect available character IDs and background IDs
    char_ids = [c["id"] for c in story.get("characters", [])]
    char_info = ", ".join(
        f'{c["id"]} ("{c["name"]}")'
        for c in story.get("characters", [])
    )
    bg_ids = [b["id"] for b in story.get("backgrounds", [])]

    current_bg = "meadow"
    current_puppets = []
    if current_scene:
        current_bg = current_scene.get("background_id", "meadow")
        current_puppets = current_scene.get("puppets", [])

    puppet_positions = ""
    if current_puppets:
        puppet_positions = json.dumps(current_puppets)
    else:
        puppet_positions = "unknown"

    return f"""You are a puppet stage controller. A child just said something during an interactive story.
Based on what the child said, generate the appropriate puppet stage commands as JSON.

STORY: "{story.get('title', 'Unknown')}"
CHARACTERS: {char_info}
BACKGROUNDS: {json.dumps(bg_ids)}
CURRENT SCENE: background="{current_bg}", puppets={puppet_positions}

CHILD SAID: "{child_text}"

Generate a JSON response with EXACTLY this structure:
{{
  "needs_scene_change": true/false,
  "set_scene": {{
    "background_id": "<one of the available backgrounds>",
    "mood": "<emotional mood>",
    "puppets": [
      {{"character_id": "<id>", "x": <0-100>, "y": <60-70>}}
    ]
  }},
  "action_sequence": {{
    "duration": <2-5>,
    "animations": [
      {{
        "character_id": "<id>",
        "keyframes": [
          {{"t": 0, "x": <start_x>, "y": <start_y>}},
          {{"t": <mid>, "x": <mid_x>, "y": <mid_y>, "rotation": <opt>, "scale": <opt>}},
          {{"t": <end>, "x": <end_x>, "y": <end_y>}}
        ],
        "easing": "easeInOut"
      }}
    ]
  }}
}}

Rules:
- If the child requests a CHANGE (new character behavior, scene change), set needs_scene_change=true and update set_scene.
- If the child asks a QUESTION, set needs_scene_change=false but still animate a character reacting (gesturing, tilting head).
- If the child SUGGESTS an action (dance, jump, etc.), animate ALL relevant characters doing that action.
- Use ONLY character IDs from the available list: {json.dumps(char_ids)}
- Use ONLY background IDs from the available list: {json.dumps(bg_ids)}
- Keep current positions unless the child's request requires repositioning.
- Respond with ONLY the JSON, no markdown, no explanation."""


async def infer_puppet_commands(
    child_text: str,
    story: dict,
    current_scene: dict | None = None,
) -> dict | None:
    """Call Gemini text API to infer puppet commands for a child's request.
    
    Returns a dict with 'set_scene' and/or 'action_sequence' data,
    or None if inference fails.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[PuppetInference] No API key found")
        return None

    prompt = _build_inference_prompt(child_text, story, current_scene)
    
    t0 = time.monotonic()
    try:
        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model=INFERENCE_MODEL,
            contents=prompt,
            config={
                "temperature": 0.3,  # low temp for deterministic output
                "max_output_tokens": 800,
            },
        )

        elapsed = time.monotonic() - t0
        raw = response.text.strip()
        
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        result = json.loads(raw)
        print(f"[PuppetInference] Generated commands in {elapsed:.2f}s: "
              f"scene_change={result.get('needs_scene_change')}, "
              f"animations={len(result.get('action_sequence', {}).get('animations', []))}")
        return result

    except json.JSONDecodeError as e:
        elapsed = time.monotonic() - t0
        print(f"[PuppetInference] JSON parse error after {elapsed:.2f}s: {e}")
        print(f"[PuppetInference] Raw response: {raw[:200] if 'raw' in dir() else 'N/A'}")
        return None
    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"[PuppetInference] Error after {elapsed:.2f}s: {e}")
        return None
