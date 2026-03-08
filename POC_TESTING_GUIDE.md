# Dream Weaver — POC Testing Guide

## Prerequisites

1. **API Key** — Ensure `PuppetStory/.env` contains:
   ```
   GOOGLE_API_KEY=your_key_here
   ```
2. **Backend deps installed**:
   ```bash
   cd backend && pip install -r requirements.txt
   ```
3. **Frontend deps installed**:
   ```bash
   cd frontend && npm install
   ```

---

## Starting the App

Open **two terminals**:

### Terminal 1 — Backend (port 8000)
```bash
cd backend
uvicorn server:app --host 0.0.0.0 --port 8000
```
You should see: `Uvicorn running on http://0.0.0.0:8000`

### Terminal 2 — Frontend (port 5173)
```bash
cd frontend
npm run dev
```
You should see: `VITE ready` with `http://localhost:5173/`

### Open in Browser
Go to **http://localhost:5173** (use Chrome for best TTS/audio support).

---

## Option A: Automated Demo (Recommended for first test)

1. Click **🎬 Run Demo**
2. Sit back and watch — the demo auto-sends 6 scripted prompts:

| Step | Time | Who | What Happens |
|------|------|-----|-------------|
| 1 | 0:02 | Parent | "Hello Dream Weaver! My child wants a bedtime story tonight." |
| 2 | 0:17 | Child | "I want a story about a PINK DRAGON that lives on a snowy mountain!" |
| 3 | 0:37 | Child | "And the dragon should have sparkly wings and be really friendly!" |
| 4 | 0:57 | Child | "No wait! The dragon should blow RAINBOW BUBBLES instead of fire!" |
| 5 | 1:17 | Child | "Can a little bunny come ride on the dragon? A fluffy white bunny!" |
| 6 | 1:37 | Parent | Sleepy time signal — story winds down |

### What to look for:
- **Purple banner at top** shows which demo step is active
- **Audio plays** — Gemini narrates the story aloud
- **Browser TTS** speaks narration text (if Gemini returns text instead of audio)
- **Stage background changes** — gradient shifts to match mood (magical = purple/pink)
- **Scene elements appear** — Gemini-generated watercolor illustrations animate on stage
- **Transcript panel** (right side) shows narrator's words streaming in
- **Animations** — elements bob, float, pulse based on the scene data

3. Click **⏹ Stop** when done.

---

## Option B: Live Mic Mode (Full interactive demo)

### Setup
1. Click **🎤 Live Mode (Mic)**
2. **Allow microphone** when the browser asks
3. Use **headphones** to avoid echo (the AI will hear its own voice otherwise)

### Step-by-Step Script

Follow this script with **two people** (Parent + Child) or do both voices yourself:

---

#### ACT 1 — The Greeting (0:00–0:30)

**Parent says:**
> "Hello! We're ready for a bedtime story tonight."

*Wait for Dream Weaver to greet you and ask what kind of story the child wants.*

**What to watch:** Stage shows moon/stars idle screen, narrator voice plays warmly.

---

#### ACT 2 — The Setup (0:30–1:30)

**Child says (excited):**
> "I want a story about a pink dragon! A really friendly one that lives on a big snowy mountain!"

*Wait ~15 seconds. Dream Weaver starts narrating and generates the first scene.*

**What to watch:**
- Stage background shifts to **magical** gradient (purple/pink/gold)
- **Pink dragon** illustration appears, gently bobbing
- **Snowy mountain** background appears behind it
- Narrator introduces the dragon with a name and personality

---

#### ACT 3 — The First Interruption (1:30–2:30)

**Child interrupts (excited):**
> "And the dragon should blow rainbow BUBBLES instead of fire! Big sparkly bubbles!"

*Dream Weaver adapts the story on the fly.*

**What to watch:**
- Narrator acknowledges the idea mid-story
- New **bubble elements** may appear on stage with pulse/float animations
- Story pivots to include rainbow bubbles

**Child adds:**
> "The bubbles should make flowers grow everywhere!"

*Wait for the story to incorporate this.*

---

#### ACT 4 — Adding a Friend (2:30–3:30)

**Child says:**
> "Can a little bunny come ride on the dragon? A fluffy white bunny named Snowball!"

**What to watch:**
- New **bunny character** generated and placed on stage
- Narrator weaves the bunny into the story
- Scene may update with new element positions

---

#### ACT 5 — A Plot Twist (3:30–4:30)

**Child says (dramatic):**
> "Oh no! A big storm cloud is coming! The dragon has to protect the bunny!"

**What to watch:**
- Mood may shift to **mysterious** (darker gradient)
- Storm cloud element may appear
- Narrator builds gentle tension (but keeps it kid-friendly)

**Child says:**
> "The dragon blows a GIANT bubble to make a bubble shield!"

**What to watch:**
- Story resolves with the bubble shield idea
- Mood shifts back to **magical** or **calm**

---

#### ACT 6 — Wind Down (4:30–5:30)

**Parent clicks 😴 Sleepy Time** (or says):
> "Time to wind down the story, it's getting sleepy."

**What to watch:**
- Narrator slows pace, voice becomes gentler
- Mood shifts to **sleepy** (deep blue/purple gradient)
- Twinkling stars appear on stage
- Story brings characters to rest
- Narrator ends with a soft goodnight

---

#### ACT 7 — End

Click **⏹ Stop** to end the session.

---

## What to Demonstrate in the POC

| Feature | How It Shows |
|---------|-------------|
| **Real-time voice AI** | Gemini narrates aloud, responds to speech |
| **Child interruption** | AI pivots story mid-narration when child speaks |
| **Function calling** | `generate_scene` called automatically — visible in backend logs |
| **AI image generation** | Watercolor illustrations appear on stage (Gemini-generated) |
| **Image caching** | Same element reused across scenes without re-generating |
| **CSS puppet animations** | Elements bob, float, pulse on the stage |
| **Mood-based staging** | Background gradient changes with story mood |
| **Transcript** | Real-time text of what narrator says (toggle with button) |
| **Wind-down flow** | Parent signals sleepy time, story calms down |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No audio plays | Use Chrome, click somewhere on the page first (browser autoplay policy) |
| Mic not working | Check browser permissions, use headphones |
| "Disconnected" immediately | Check backend terminal for errors, ensure API key is valid |
| No scenes appearing | The AI sometimes needs 2-3 prompts before calling `generate_scene` — keep talking |
| Images are placeholders | Image gen may fail — check backend logs for errors |
| Echo/feedback loop | Use headphones so the AI doesn't hear itself |

---

## Backend Logs to Watch

In the backend terminal you'll see real-time logs:
```
[Server] User text: I want a story about a pink dragon...
[Server] generate_scene: Pink Dragon on Snowy Mountain
[Server]   mood=magical, elements=2
[ImageGen] Generating: pink_dragon_body — ...
[ImageGen] ✅ Generated pink_dragon_body (937KB -> 237KB)
```

These confirm the full pipeline: voice → Gemini → function calling → image generation → frontend.
