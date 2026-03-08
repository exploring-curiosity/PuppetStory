"""
Image Generator — Gemini image generation with in-memory caching.
Supports fast_mode with rich SVG puppets for instant testing.
Falls back to colored SVG placeholders if generation fails.
"""

import asyncio
import base64
import hashlib
import io
import math
import traceback
from google import genai
from google.genai import types


IMAGE_MODEL = "gemini-2.0-flash-exp-image-generation"

# ─── SVG puppet templates for fast mode ─────────────────────────────────
# These are rich, colorful SVG illustrations that render instantly

def _svg_puppet(el_id: str, description: str) -> str:
    """Generate a rich SVG puppet based on keywords in the description."""
    desc = (description or el_id).lower()
    h = hashlib.md5(el_id.encode()).hexdigest()

    # Pick colors and shape based on description keywords
    if "dragon" in desc or "dinosaur" in desc:
        body_color = "#FF69B4" if "pink" in desc else "#4CAF50"
        accent = "#FFD700"
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  <defs><filter id="s{h[:4]}"><feGaussianBlur stdDeviation="2"/></filter></defs>
  <!-- Body -->
  <ellipse cx="200" cy="230" rx="100" ry="80" fill="{body_color}" filter="url(#s{h[:4]})"/>
  <!-- Belly -->
  <ellipse cx="200" cy="250" rx="65" ry="55" fill="{body_color}" opacity="0.6"/>
  <ellipse cx="200" cy="250" rx="55" ry="45" fill="#FFE4E1"/>
  <!-- Head -->
  <circle cx="200" cy="140" r="55" fill="{body_color}"/>
  <!-- Eyes -->
  <circle cx="180" cy="130" r="18" fill="white"/>
  <circle cx="220" cy="130" r="18" fill="white"/>
  <circle cx="183" cy="128" r="10" fill="#333"/>
  <circle cx="223" cy="128" r="10" fill="#333"/>
  <circle cx="186" cy="124" r="4" fill="white"/>
  <circle cx="226" cy="124" r="4" fill="white"/>
  <!-- Smile -->
  <path d="M175 155 Q200 180 225 155" fill="none" stroke="#333" stroke-width="3" stroke-linecap="round"/>
  <!-- Wings -->
  <path d="M100 200 Q50 140 80 100 Q100 130 120 180Z" fill="{accent}" opacity="0.8"/>
  <path d="M300 200 Q350 140 320 100 Q300 130 280 180Z" fill="{accent}" opacity="0.8"/>
  <!-- Sparkles on wings -->
  <circle cx="80" cy="140" r="4" fill="white" opacity="0.9"/>
  <circle cx="320" cy="140" r="4" fill="white" opacity="0.9"/>
  <circle cx="70" cy="120" r="3" fill="white" opacity="0.7"/>
  <circle cx="330" cy="120" r="3" fill="white" opacity="0.7"/>
  <!-- Horns -->
  <path d="M175 95 L165 55 L185 85Z" fill="{accent}"/>
  <path d="M225 95 L235 55 L215 85Z" fill="{accent}"/>
  <!-- Tail -->
  <path d="M290 260 Q340 280 350 240 Q360 220 340 230" fill="{body_color}" stroke="{body_color}" stroke-width="8" stroke-linecap="round" fill="none"/>
  <!-- Feet -->
  <ellipse cx="155" cy="310" rx="25" ry="12" fill="{body_color}"/>
  <ellipse cx="245" cy="310" rx="25" ry="12" fill="{body_color}"/>
</svg>'''

    elif "bunny" in desc or "rabbit" in desc:
        fur = "#FFFFFF" if "white" in desc else "#D2B48C"
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  <!-- Ears -->
  <ellipse cx="170" cy="80" rx="22" ry="65" fill="{fur}" stroke="#DDD" stroke-width="2"/>
  <ellipse cx="170" cy="80" rx="12" ry="50" fill="#FFB6C1"/>
  <ellipse cx="230" cy="80" rx="22" ry="65" fill="{fur}" stroke="#DDD" stroke-width="2"/>
  <ellipse cx="230" cy="80" rx="12" ry="50" fill="#FFB6C1"/>
  <!-- Body -->
  <ellipse cx="200" cy="270" rx="80" ry="90" fill="{fur}" stroke="#DDD" stroke-width="2"/>
  <!-- Head -->
  <circle cx="200" cy="170" r="60" fill="{fur}" stroke="#DDD" stroke-width="2"/>
  <!-- Eyes -->
  <circle cx="180" cy="160" r="12" fill="#333"/>
  <circle cx="220" cy="160" r="12" fill="#333"/>
  <circle cx="184" cy="156" r="5" fill="white"/>
  <circle cx="224" cy="156" r="5" fill="white"/>
  <!-- Nose -->
  <ellipse cx="200" cy="180" rx="8" ry="6" fill="#FFB6C1"/>
  <!-- Whiskers -->
  <line x1="155" y1="178" x2="125" y2="172" stroke="#CCC" stroke-width="1.5"/>
  <line x1="155" y1="183" x2="125" y2="187" stroke="#CCC" stroke-width="1.5"/>
  <line x1="245" y1="178" x2="275" y2="172" stroke="#CCC" stroke-width="1.5"/>
  <line x1="245" y1="183" x2="275" y2="187" stroke="#CCC" stroke-width="1.5"/>
  <!-- Mouth -->
  <path d="M192 188 Q200 196 208 188" fill="none" stroke="#CCC" stroke-width="1.5"/>
  <!-- Paws -->
  <ellipse cx="155" cy="340" rx="22" ry="14" fill="{fur}" stroke="#DDD" stroke-width="2"/>
  <ellipse cx="245" cy="340" rx="22" ry="14" fill="{fur}" stroke="#DDD" stroke-width="2"/>
  <!-- Tail -->
  <circle cx="275" cy="290" r="18" fill="{fur}" stroke="#DDD" stroke-width="2"/>
</svg>'''

    elif "bubble" in desc:
        colors = ["#FF69B4", "#FF4500", "#FFD700", "#4CAF50", "#2196F3", "#9C27B0"]
        circles = ""
        for i in range(8):
            cx = 80 + (i % 4) * 80
            cy = 80 + (i // 4) * 160 + (i * 23 % 60)
            r = 30 + (i * 17 % 25)
            c = colors[i % len(colors)]
            circles += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}" opacity="0.4" stroke="{c}" stroke-width="2"/>\n'
            circles += f'<circle cx="{cx-r//3}" cy="{cy-r//3}" r="{r//4}" fill="white" opacity="0.6"/>\n'
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  {circles}
</svg>'''

    elif "flower" in desc or "garden" in desc:
        petals = ""
        colors = ["#FF69B4", "#FF4500", "#FFD700", "#E91E63", "#FF5722"]
        for i in range(5):
            cx = 70 + i * 70
            cy = 200 + (i * 37 % 80) - 40
            c = colors[i % len(colors)]
            for a in range(5):
                angle = a * 72
                px = cx + 20 * math.cos(math.radians(angle))
                py = cy + 20 * math.sin(math.radians(angle))
                petals += f'<circle cx="{px:.0f}" cy="{py:.0f}" r="14" fill="{c}" opacity="0.8"/>\n'
            petals += f'<circle cx="{cx}" cy="{cy}" r="10" fill="#FFD700"/>\n'
            petals += f'<line x1="{cx}" y1="{cy+14}" x2="{cx}" y2="{cy+80}" stroke="#4CAF50" stroke-width="4"/>\n'
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  {petals}
</svg>'''

    elif "star" in desc or "sparkle" in desc:
        stars = ""
        for i in range(12):
            cx = 40 + (i * 73 % 320)
            cy = 40 + (i * 53 % 320)
            s = 8 + i * 3 % 15
            op = 0.5 + (i % 3) * 0.2
            stars += f'<polygon points="{cx},{cy-s} {cx+s//3},{cy-s//3} {cx+s},{cy} {cx+s//3},{cy+s//3} {cx},{cy+s} {cx-s//3},{cy+s//3} {cx-s},{cy} {cx-s//3},{cy-s//3}" fill="#FFD700" opacity="{op}"/>\n'
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  {stars}
</svg>'''

    else:
        # Generic friendly character
        c1 = f"#{h[:2]}88{h[2:4]}"
        c2 = f"#{h[4:6]}55{h[6:8]}"
        label_text = el_id.replace("_", " ")[:16]
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  <!-- Body -->
  <ellipse cx="200" cy="250" rx="90" ry="100" fill="{c1}"/>
  <ellipse cx="200" cy="270" rx="60" ry="65" fill="{c2}" opacity="0.5"/>
  <!-- Head -->
  <circle cx="200" cy="140" r="60" fill="{c1}"/>
  <!-- Eyes -->
  <circle cx="178" cy="130" r="15" fill="white"/>
  <circle cx="222" cy="130" r="15" fill="white"/>
  <circle cx="181" cy="128" r="8" fill="#333"/>
  <circle cx="225" cy="128" r="8" fill="#333"/>
  <circle cx="184" cy="124" r="3" fill="white"/>
  <circle cx="228" cy="124" r="3" fill="white"/>
  <!-- Smile -->
  <path d="M175 160 Q200 185 225 160" fill="none" stroke="#333" stroke-width="3" stroke-linecap="round"/>
  <!-- Arms -->
  <ellipse cx="105" cy="230" rx="20" ry="40" fill="{c1}" transform="rotate(-15 105 230)"/>
  <ellipse cx="295" cy="230" rx="20" ry="40" fill="{c1}" transform="rotate(15 295 230)"/>
  <!-- Feet -->
  <ellipse cx="160" cy="345" rx="30" ry="15" fill="{c1}"/>
  <ellipse cx="240" cy="345" rx="30" ry="15" fill="{c1}"/>
  <!-- Label -->
  <text x="200" y="385" text-anchor="middle" fill="white" font-family="Georgia,serif" font-size="14" opacity="0.7">{label_text}</text>
</svg>'''


def _svg_background(el_id: str, description: str) -> str:
    """Generate a rich SVG background based on description keywords."""
    desc = (description or el_id).lower()

    if "snow" in desc or "mountain" in desc or "winter" in desc:
        return '''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0c1445"/>
      <stop offset="50%" stop-color="#1a237e"/>
      <stop offset="100%" stop-color="#4a148c"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="800" fill="url(#sky)"/>
  <!-- Stars -->
  <circle cx="100" cy="50" r="2" fill="white" opacity="0.8"/>
  <circle cx="300" cy="80" r="1.5" fill="white" opacity="0.6"/>
  <circle cx="500" cy="40" r="2" fill="white" opacity="0.9"/>
  <circle cx="700" cy="90" r="1" fill="white" opacity="0.5"/>
  <circle cx="900" cy="30" r="2.5" fill="white" opacity="0.7"/>
  <circle cx="1100" cy="70" r="1.5" fill="white" opacity="0.8"/>
  <circle cx="200" cy="120" r="1" fill="white" opacity="0.6"/>
  <circle cx="800" cy="60" r="2" fill="white" opacity="0.7"/>
  <!-- Moon -->
  <circle cx="950" cy="120" r="45" fill="#FFF9C4" opacity="0.9"/>
  <circle cx="935" cy="110" r="40" fill="#0c1445" opacity="0.7"/>
  <!-- Mountains -->
  <polygon points="0,500 200,250 400,500" fill="#37474f"/>
  <polygon points="250,500 500,200 750,500" fill="#455a64"/>
  <polygon points="600,500 850,280 1100,500" fill="#37474f"/>
  <polygon points="900,500 1100,300 1200,400 1200,500" fill="#455a64"/>
  <!-- Snow caps -->
  <polygon points="170,290 200,250 230,290" fill="white" opacity="0.9"/>
  <polygon points="460,240 500,200 540,240" fill="white" opacity="0.9"/>
  <polygon points="815,320 850,280 885,320" fill="white" opacity="0.9"/>
  <!-- Snow ground -->
  <ellipse cx="600" cy="700" rx="800" ry="250" fill="white" opacity="0.95"/>
  <!-- Pine trees -->
  <polygon points="150,480 170,400 190,480" fill="#1b5e20" opacity="0.7"/>
  <polygon points="750,470 770,380 790,470" fill="#1b5e20" opacity="0.7"/>
  <polygon points="350,490 365,420 380,490" fill="#2e7d32" opacity="0.6"/>
</svg>'''

    elif "forest" in desc or "tree" in desc or "wood" in desc:
        return '''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
  <defs>
    <linearGradient id="fsky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#81C784"/>
      <stop offset="100%" stop-color="#2E7D32"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="800" fill="url(#fsky)"/>
  <rect y="500" width="1200" height="300" fill="#4CAF50" opacity="0.6"/>
  <!-- Trees -->
  <rect x="90" y="300" width="20" height="200" fill="#5D4037"/>
  <polygon points="30,320 100,180 170,320" fill="#2E7D32"/>
  <polygon points="40,260 100,140 160,260" fill="#388E3C"/>
  <rect x="290" y="280" width="20" height="220" fill="#5D4037"/>
  <polygon points="220,300 300,150 380,300" fill="#1B5E20"/>
  <polygon points="235,230 300,100 365,230" fill="#2E7D32"/>
  <rect x="590" y="320" width="20" height="180" fill="#5D4037"/>
  <polygon points="530,340 600,200 670,340" fill="#2E7D32"/>
  <rect x="890" y="290" width="20" height="210" fill="#5D4037"/>
  <polygon points="830,310 900,160 970,310" fill="#1B5E20"/>
  <polygon points="840,240 900,110 960,240" fill="#2E7D32"/>
  <!-- Flowers -->
  <circle cx="200" cy="600" r="8" fill="#FF69B4"/>
  <circle cx="500" cy="580" r="6" fill="#FFD700"/>
  <circle cx="800" cy="610" r="7" fill="#E91E63"/>
  <circle cx="1000" cy="590" r="5" fill="#FF9800"/>
</svg>'''

    else:
        # Generic dreamy background
        return '''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
  <defs>
    <linearGradient id="gsky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#a18cd1"/>
      <stop offset="40%" stop-color="#fbc2eb"/>
      <stop offset="100%" stop-color="#f6d365"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="800" fill="url(#gsky)"/>
  <!-- Clouds -->
  <ellipse cx="200" cy="150" rx="100" ry="40" fill="white" opacity="0.7"/>
  <ellipse cx="250" cy="140" rx="70" ry="35" fill="white" opacity="0.8"/>
  <ellipse cx="800" cy="120" rx="120" ry="45" fill="white" opacity="0.6"/>
  <ellipse cx="860" cy="110" rx="80" ry="35" fill="white" opacity="0.7"/>
  <!-- Rolling hills -->
  <ellipse cx="300" cy="750" rx="500" ry="200" fill="#81C784" opacity="0.6"/>
  <ellipse cx="900" cy="780" rx="500" ry="180" fill="#A5D6A7" opacity="0.5"/>
  <ellipse cx="600" cy="800" rx="700" ry="150" fill="#C8E6C9" opacity="0.7"/>
</svg>'''


class ImageGenerator:
    def __init__(self, api_key: str, fast_mode: bool = False):
        self.client = genai.Client(api_key=api_key)
        self.cache: dict[str, str] = {}
        self.fast_mode = fast_mode
        if fast_mode:
            print("[ImageGen] ⚡ Fast mode enabled — using SVG puppets (no API calls)")

    async def process_scene(self, scene_data: dict) -> dict:
        """
        Process a scene from generate_scene function call.
        For each element with is_new=True and a description, generates an image.
        Cached elements are reused. Attaches base64 data URIs to each element.
        """
        elements = scene_data.get("elements", [])

        # Collect elements that need generation
        tasks = []
        for el in elements:
            el_id = el.get("id", "unknown")
            if el_id in self.cache and not el.get("is_new"):
                el["image"] = self.cache[el_id]
            elif el.get("description"):
                tasks.append(el)
            else:
                el["image"] = self._make_placeholder(el_id, "")

        # Generate images (fast SVG or real Gemini)
        if tasks:
            if self.fast_mode:
                for el in tasks:
                    el_id = el.get("id", "unknown")
                    desc = el.get("description", "")
                    is_bg = self._is_background(el)
                    if is_bg:
                        svg = _svg_background(el_id, desc)
                    else:
                        svg = _svg_puppet(el_id, desc)
                    b64 = base64.b64encode(svg.encode()).decode()
                    el["image"] = f"data:image/svg+xml;base64,{b64}"
                    self.cache[el_id] = el["image"]
                    print(f"[ImageGen] ⚡ SVG {'BG' if is_bg else 'PUPPET'}: {el_id}")
            else:
                results = await asyncio.gather(
                    *[self._generate_image(el) for el in tasks],
                    return_exceptions=True
                )
                for el, result in zip(tasks, results):
                    if isinstance(result, Exception):
                        print(f"[ImageGen] Failed for {el.get('id')}: {result}")
                        el["image"] = self._make_placeholder(el.get("id", "err"), el.get("description", ""))
                    else:
                        el["image"] = result
                        self.cache[el["id"]] = result

        return scene_data

    def _is_background(self, element: dict) -> bool:
        """Detect if this element is a scene background vs a puppet/character."""
        z = element.get("z_index", 5)
        # z_index > 0 is definitely a puppet, regardless of name
        if z > 0:
            return False
        # z_index == 0: check keywords to confirm
        el_id = (element.get("id") or "").lower()
        bg_keywords = ["background", "backdrop", "scenery", "landscape", "environment", "setting"]
        if any(kw in el_id for kw in bg_keywords):
            return True
        # z_index == 0 but no keyword match — still treat as background
        return z == 0

    async def _generate_image(self, element: dict) -> str:
        """Generate an image for a single element using Gemini."""
        el_id = element.get("id", "unknown")
        description = element.get("description", "")
        is_bg = self._is_background(element)

        if is_bg:
            prompt = (
                f"Generate a wide panoramic children's book illustration for a scene background: {description}. "
                f"Style: soft watercolor, dreamy, colorful, wide landscape format. Fill the entire image. No text. No characters."
            )
        else:
            prompt = (
                f"Generate a children's book puppet character illustration: {description}. "
                f"Style: soft watercolor, friendly, colorful. The character must be isolated on a pure white (#FFFFFF) background "
                f"with no shadows, no ground, no scenery. Just the character/object alone. No text."
            )

        print(f"[ImageGen] Generating {'BG' if is_bg else 'PUPPET'}: {el_id} — {description[:60]}...")

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=IMAGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                )
            )

            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                        img_bytes = part.inline_data.data
                        resized = await asyncio.to_thread(self._resize_image, img_bytes, 512, is_bg)
                        b64 = base64.b64encode(resized).decode()
                        mime = "image/jpeg" if is_bg else "image/png"
                        data_uri = f"data:{mime};base64,{b64}"
                        print(f"[ImageGen] ✅ Generated {el_id} ({len(img_bytes)//1024}KB -> {len(resized)//1024}KB)")
                        return data_uri

            print(f"[ImageGen] ⚠️ No image in response for {el_id}, using placeholder")
            return self._make_placeholder(el_id, description)

        except Exception as e:
            print(f"[ImageGen] ❌ Error generating {el_id}: {e}")
            return self._make_placeholder(el_id, description)

    def _resize_image(self, img_bytes: bytes, max_size: int = 512, is_bg: bool = False) -> bytes:
        """Resize and process image. Backgrounds keep as-is, puppets get white removed for transparency."""
        from PIL import Image
        import numpy as np
        img = Image.open(io.BytesIO(img_bytes))

        if is_bg:
            img.thumbnail((1024, 768), Image.LANCZOS)
            if img.mode != "RGB":
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            return buf.getvalue()
        else:
            img.thumbnail((max_size, max_size), Image.LANCZOS)
            img = img.convert("RGBA")
            data = np.array(img)
            r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
            white_mask = (r > 210) & (g > 210) & (b > 210)
            from scipy.ndimage import label, binary_dilation
            labeled, num_features = label(white_mask)
            edge_labels = set()
            h, w = white_mask.shape
            for lbl_arr in [labeled[0,:], labeled[-1,:], labeled[:,0], labeled[:,-1]]:
                edge_labels.update(lbl_arr[lbl_arr > 0].tolist())
            bg_mask = np.zeros_like(white_mask)
            for lbl in edge_labels:
                bg_mask |= (labeled == lbl)
            data[bg_mask, 3] = 0
            edge_band = binary_dilation(bg_mask, iterations=2) & ~bg_mask
            data[edge_band, 3] = (data[edge_band, 3] * 0.4).astype(np.uint8)
            img = Image.fromarray(data)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            return buf.getvalue()

    def _make_placeholder(self, el_id: str, description: str) -> str:
        """Create a simple SVG placeholder with the element name."""
        h = hashlib.md5(el_id.encode()).hexdigest()
        color = f"#{h[:6]}"
        label = el_id.replace("_", " ")[:20]
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect width="256" height="256" fill="{color}" rx="16" opacity="0.7"/>
  <text x="128" y="120" text-anchor="middle" fill="white" font-family="sans-serif" font-size="16" font-weight="bold">{label}</text>
  <text x="128" y="150" text-anchor="middle" fill="white" font-family="sans-serif" font-size="10" opacity="0.7">(placeholder)</text>
</svg>"""
        b64 = base64.b64encode(svg.encode()).decode()
        return f"data:image/svg+xml;base64,{b64}"
