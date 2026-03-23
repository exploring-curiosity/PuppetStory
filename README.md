# PuppetStory — Interactive AI Puppet Theater for Bedtime Stories

> *"Hello there, little dreamer! I'm Dream Weaver, your magical storyteller..."*

Dream Weaver is an AI-powered interactive bedtime storytelling experience that combines **real-time voice conversation** with a **live puppet theater stage**. A child speaks naturally with an AI narrator who weaves their ideas into an evolving story — complete with animated puppet characters, scenic backdrops, and enchanting narration — all unfolding in real time on screen.

Think of it as a digital puppet show where the child is the co-author, the AI is the storyteller, and the puppets dance to life as the story unfolds.

---

## 🎭 The Experience

A typical session flows like this:

1. **The child connects** and Dream Weaver greets them warmly, asking what kind of adventure they'd like.
2. **The child says** *"I want a story about a PINK DRAGON on a snowy mountain!"*
3. **Dream Weaver narrates** the opening scene in a warm, expressive voice while a snowy mountain backdrop fills the screen and a pink dragon puppet appears on stage with a gentle bobbing animation.
4. **The child interrupts** — *"No wait! The dragon should blow RAINBOW BUBBLES instead of fire!"* — and Dream Weaver immediately pivots, incorporating the new idea seamlessly.
5. **New puppets appear** as characters are introduced — a fluffy white bunny named Snowball rides atop the dragon.
6. **A parent says** *"sleepy time"* and the story gently winds down with calming imagery, soft tones, and a peaceful goodnight.

The entire experience — voice, visuals, animations — happens in real time with no loading screens. The child's imagination drives the story forward.

---

## 🏗️ Architecture

```
┌──────────────────────┐         WebSocket          ┌──────────────────────────────┐
│     React Frontend   │ ◄──────────────────────►   │     FastAPI Backend           │
│                      │   audio (PCM binary)        │                              │
│  ┌────────────────┐  │   scene (JSON)              │  ┌────────────────────────┐  │
│  │  StoryStage    │  │   transcripts               │  │  LiveSession           │  │
│  │  (puppet stage)│  │   turn_complete             │  │  (Gemini Live API)     │  │
│  └────────────────┘  │                              │  └────────┬───────────────┘  │
│  ┌────────────────┐  │                              │           │                  │
│  │  useAudio      │  │                              │  ┌────────▼───────────────┐  │
│  │  (ring buffer) │  │                              │  │  ImageGenerator        │  │
│  └────────────────┘  │                              │  │  (Gemini / SVG fast)   │  │
│  ┌────────────────┐  │                              │  └────────────────────────┘  │
│  │  Transcript    │  │                              │  ┌────────────────────────┐  │
│  │  Panel         │  │                              │  │  System Prompt         │  │
│  └────────────────┘  │                              │  │  (Dream Weaver persona)│  │
└──────────────────────┘                              └──────────────────────────────┘
                                                                │
                                                      ┌────────▼────────┐
                                                      │  Google Gemini   │
                                                      │  Live API        │
                                                      │  (voice + tools) │
                                                      └─────────────────┘
```

### Data Flow

1. **User speaks** → mic captured as 16kHz PCM → sent as binary WebSocket frames to backend
2. **Backend streams PCM** to Gemini Live API session (bidirectional real-time audio)
3. **Gemini narrates** → 24kHz PCM audio streamed back → forwarded to frontend as binary frames
4. **Gemini calls `generate_scene`** function → backend generates/caches images → scene JSON sent to frontend
5. **Frontend renders** scene: background fills the stage, puppet elements overlay with CSS animations
6. **Frontend plays audio** through a ring buffer + ScriptProcessorNode for gapless streaming playback

---

## 🛠️ Tech Stack

### Backend (Python)

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Web Framework** | FastAPI | WebSocket server, REST health endpoint |
| **AI Model** | Gemini 2.5 Flash (Native Audio Preview) | Real-time voice conversation via Live API |
| **Image Generation** | Gemini 2.0 Flash (Exp Image Generation) | Watercolor-style puppet & background illustrations |
| **Fast Mode** | Hand-crafted SVG templates | Instant puppet rendering without API calls (for testing) |
| **Image Processing** | Pillow, NumPy, SciPy | Background removal via edge-connected flood fill |
| **Server** | Uvicorn | ASGI server |

### Frontend (TypeScript)

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | React 19 + TypeScript | UI components and state management |
| **Build Tool** | Vite 7 | Development server with HMR |
| **Audio Capture** | Web Audio API (ScriptProcessorNode) | 16kHz mono PCM mic capture |
| **Audio Playback** | Ring Buffer + ScriptProcessorNode | Gapless 24kHz PCM streaming (zero jitter) |
| **Animations** | Pure CSS keyframes | 14 animation types for puppet movement |
| **Scene Rendering** | CSS absolute positioning | z-index layered stage with fullscreen backgrounds |

### APIs & Protocols

| Protocol | Usage |
|----------|-------|
| **WebSocket** | Bidirectional real-time audio + JSON messaging |
| **Gemini Live API** | Server-to-server streaming audio + function calling |
| **Web Audio API** | Browser-side audio capture and playback |

---

## 📁 Project Structure

```
PuppetStory/
├── backend/
│   ├── server.py              # FastAPI WebSocket endpoint — bridges browser ↔ Gemini
│   ├── live_session.py        # Gemini Live API wrapper — manages audio streaming & tool calls
│   ├── image_generator.py     # Image generation — Gemini API or instant SVG fast mode
│   ├── system_prompt.py       # Dream Weaver persona, story structure, scene generation rules
│   ├── requirements.txt       # Python dependencies
│   ├── test_e2e.py            # End-to-end WebSocket test script
│   └── test_demo_flow.py      # Automated demo flow test
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx            # Main app — demo mode orchestration, speech bubbles, controls
│   │   ├── hooks/
│   │   │   ├── useStorySocket.ts   # WebSocket hook — manages connection, audio, scenes, transcripts
│   │   │   └── useAudio.ts         # Audio hook — ring buffer playback, mic capture, stop control
│   │   ├── components/
│   │   │   ├── StoryStage.tsx      # Puppet stage — fullscreen backgrounds + positioned puppets
│   │   │   ├── SceneElement.tsx    # Individual puppet — animated, scaled, positioned
│   │   │   ├── Transcript.tsx      # Live transcript panel
│   │   │   └── ControlBar.tsx      # Demo/live mode controls
│   │   └── styles/
│   │       ├── stage.css           # Stage layout, mood gradients, transitions
│   │       └── animations.css      # 14 puppet animations (bob, float, shake, spin, etc.)
│   ├── package.json
│   └── vite.config.ts
│
├── .env                       # GOOGLE_API_KEY + FAST_MODE flag
├── .gitignore
├── POC_TESTING_GUIDE.md       # Step-by-step demo testing instructions
└── README.md                  # This file
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Google AI API Key** with access to Gemini models

### 1. Clone & Configure

```bash
git clone https://github.com/exploring-curiosity/PuppetStory.git
cd PuppetStory

# Create your .env file
cp backend/.env.example .env
# Edit .env and add your Google API key:
#   GOOGLE_API_KEY=your_key_here
#   FAST_MODE=true        # SVG puppets (instant, no API cost)
#   FAST_MODE=false       # Real Gemini image generation (slower, richer visuals)
```

### 2. Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 4. Open the App

Navigate to **http://localhost:5173** and click **🎬 Run Demo** to see the full experience.

---

## 🎬 Demo Mode

The built-in demo simulates a realistic parent-child bedtime story session. It sends scripted prompts with proper turn-taking:

| Step | Speaker | Text | What Happens |
|------|---------|------|-------------|
| 1 | Parent | *"Hello Dream Weaver! My child wants a bedtime story tonight."* | AI greets warmly, asks what adventure they want |
| 2 | Child | *"I want a story about a PINK DRAGON on a snowy mountain!"* | Scene generates: snowy mountain backdrop + pink dragon puppet |
| 3 | Child | *"The dragon should have sparkly wings and be really friendly!"* | AI elaborates, scene may update |
| 4 | Child | *"No wait! Rainbow bubbles instead of fire!"* | **Interrupt** — narration stops, AI pivots seamlessly |
| 5 | Child | *"Can a little bunny named Snowball ride on the dragon?"* | New puppet appears: white bunny on stage |
| 6 | Parent | *"Sleepy time"* | Story winds down with calming imagery and peaceful goodnight |

The demo is **event-driven** — each step waits for the AI to finish its turn before advancing, ensuring natural pacing.

---

## 🎨 Scene & Animation System

### Scene Elements

Every scene has two types of elements:

- **Backgrounds** (`z_index: 0`) — rendered fullscreen, covering the entire stage. Identified by `"background"` in the element ID.
- **Puppets** (`z_index: 1+`) — positioned on stage at `(x%, y%)` coordinates, scaled, and animated. Transparent backgrounds via edge-connected flood-fill white removal.

### 14 Animation Types

| Animation | Use Case | Example |
|-----------|----------|---------|
| `idle_bob` | Gentle floating | Hovering dragon, standing character |
| `oscillate_y` | Vertical rotation | Wings flapping, jaw opening |
| `oscillate_x` | Horizontal rocking | Tail wagging, waving |
| `pulse_scale` | Breathing/glowing | Fire, magic effects, heartbeats |
| `translate_x` | Horizontal movement | Walking, flying across scene |
| `translate_y` | Vertical movement | Jumping, falling rain, rising smoke |
| `rotate_oscillate` | Gentle rocking | Swaying tree, rocking boat |
| `float` | Slow drifting | Clouds, bubbles, snowflakes |
| `fade_in` | Entrance | New element appearing |
| `fade_out` | Exit | Element disappearing |
| `shake` | Vibration | Scared character, impact, giggles |
| `spin` | Full rotation | Magic portals, spinning stars |
| `twinkle` | Opacity flicker | Stars, sparkles, fireflies |
| `none` | Static | Backgrounds, buildings, ground |

Each animation has configurable **speed** (slow/medium/fast) and **intensity** (0.1–1.0).

### Mood System

The stage background adapts to the story mood:

- **Exciting** — bright, vivid gradients
- **Calm** — soft, muted pastels
- **Mysterious** — dark, desaturated tones
- **Funny** — bright, exaggerated colors
- **Magical** — warm glow with purple-pink gradients + animated starfield
- **Sleepy** — dim, warm sepia tones for wind-down

---

## 🔊 Audio Architecture

The audio system uses a **ring buffer** approach for zero-jitter streaming playback:

```
Gemini API → PCM bytes → WebSocket → Ring Buffer (240K samples / 10s)
                                           ↓
                              ScriptProcessorNode pulls 4096 samples per frame
                                           ↓
                                    AudioContext output (speakers)
```

**Why not `AudioBufferSourceNode` scheduling?** Scheduling hundreds of tiny audio buffers creates gaps between them — audible as jitter, clicks, and stuttering. The ring buffer approach has a single continuous output stream that pulls from a shared buffer, guaranteeing gapless playback.

**Interrupt handling:** When the child speaks, `stopPlayback()` instantly zeros the ring buffer and tears down the audio context. The AI stops narrating and responds to the new input.

---

## 🖼️ Image Generation

### Real Mode (`FAST_MODE=false`)

Uses **Gemini 2.0 Flash Image Generation** to create watercolor-style illustrations:

- **Backgrounds** get panoramic landscape prompts → JPEG (1024×768)
- **Puppets** get isolated character prompts → white background removed via edge-connected flood fill → transparent PNG (512×512)
- Images are cached in memory — reused when a character reappears across scenes
- All images are resized to keep WebSocket frames under 1MB

### Fast Mode (`FAST_MODE=true`)

Uses **hand-crafted SVG templates** for instant rendering with zero API calls:

- **Dragon** — pink/green body with golden wings, horns, sparkly eyes, and a smile
- **Bunny** — fluffy body with pink-lined ears, whiskers, and a cotton tail
- **Bubbles** — rainbow-colored semi-transparent circles with highlights
- **Flowers** — five-petaled blooms on green stems
- **Stars/Sparkles** — golden eight-pointed star fields
- **Generic** — friendly round character with eyes and smile, auto-colored by element ID
- **Backgrounds** — snowy mountains with moon and pine trees, lush forests, dreamy gradient hills

---

## 🧠 AI Persona — Dream Weaver

Dream Weaver is designed as a magical bedtime storyteller with these traits:

- **Voice**: Warm, expressive, enchanting — like a favorite grandparent by firelight
- **Adaptability**: Matches the child's energy — dramatic for action, soft for calm moments
- **Vocabulary**: Simple, age-appropriate for 3–8 year olds
- **Sound effects**: Naturally woven in — *"WHOOOOSH!"*, *"tip-toe, tip-toe"*, *"SPLASH!"*
- **Encouragement**: Celebrates every idea — *"Oh, what a BRILLIANT idea!"*
- **Interruption handling**: Children changing their minds is wonderful, not disruptive. New ideas are incorporated immediately with smooth bridge phrases.
- **Parent authority**: A parent saying "sleepy time" triggers a gentle wind-down within 2–3 minutes
- **Safety**: All content is appropriate for ages 3–8. No scary themes. "Villains" are goofy and friendly. Problems are solved with kindness and creativity.

### Story Structure

| Act | Duration | Purpose |
|-----|----------|---------|
| **Act 1 — Setup** | ~3 min | Greeting, adventure choice, opening scene |
| **Act 2 — Adventure** | ~7 min | Challenges, discoveries, new characters, child participation |
| **Act 3 — Wind-down** | ~3 min | Calming imagery, soft tones, peaceful resolution, goodnight |

---

## ⚙️ Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | — | Google AI API key with Gemini access |
| `FAST_MODE` | No | `false` | `true` for instant SVG puppets, `false` for real Gemini image generation |

---

## 🧪 Testing

```bash
# Backend health check
curl http://localhost:8000/health

# End-to-end WebSocket test
cd backend
python test_e2e.py

# Frontend type check
cd frontend
npx tsc --noEmit
```

See [POC_TESTING_GUIDE.md](POC_TESTING_GUIDE.md) for detailed step-by-step demo testing instructions.

---

## 📋 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Ring buffer audio** (not AudioBufferSourceNode scheduling) | Eliminates jitter from scheduling hundreds of tiny audio buffers with gaps |
| **Single `response.data` audio source** (not also `model_turn.parts`) | These are the same bytes — using both caused every audio chunk to play twice |
| **Callback refs for audio wiring** (not React state) | Prevents re-render storms when streaming thousands of audio chunks per second |
| **z_index-based background detection** (not keyword matching on descriptions) | Reliable, deterministic — `z_index > 0` is always a puppet regardless of name |
| **Edge-connected flood fill for transparency** (not global threshold) | Preserves white details inside characters (eyes, teeth) while removing background |
| **SVG fast mode** | Enables instant testing of the full flow without waiting for image generation API |
| **Event-driven demo** (not timed delays) | Waits for AI turn completion before advancing — natural pacing regardless of response speed |

---

## 🔮 Future Directions

- **Live microphone mode** — real child voice input (infrastructure already built)
- **Multi-character puppetry** — articulated puppet parts (jaw, wings, tail) with independent animations
- **Persistent story memory** — remember characters and plot across sessions
- **Custom art styles** — pixel art, claymation, paper cutout, shadow puppet
- **Multiplayer** — multiple children co-authoring a story together
- **Story export** — save the story as an illustrated book or animated video

---

## 📄 License

This project is a proof of concept. See repository for license details.

---

*Built with imagination and late nights. ✨*
