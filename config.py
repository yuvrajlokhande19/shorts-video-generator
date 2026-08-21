import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"
CLIPS_DIR = ASSETS_DIR / "clips"
MUSIC_DIR = ASSETS_DIR / "music"
TEMP_DIR = BASE_DIR / "temp"

for d in (OUTPUT_DIR, ASSETS_DIR, CLIPS_DIR, MUSIC_DIR, TEMP_DIR):
    d.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

RESOLUTIONS = {
    "vertical": (1080, 1920),    # 9:16  (TikTok / Reels / Shorts)
    "horizontal": (1920, 1080),  # 16:9  (YouTube)
}

# Gradient color pairs (hex, no '#') used for procedural backgrounds.
GRADIENTS = [
    ("0x1a2a6c", "0xb21f1f"),
    ("0x0f2027", "0x2c5364"),
    ("0x42275a", "0x734b6d"),
    ("0x000428", "0x004e92"),
    ("0x16222a", "0x3a6073"),
    ("0x603813", "0xb29f94"),
    ("0x1d4350", "0xa43931"),
    ("0x0b486b", "0xf56217"),
]

FONTS_DIR = BASE_DIR / "fonts"

# Curly / handwriting display fonts bundled in fonts/ (filename -> ASS family name)
FONTS = {
    "Dancing Script": "DancingScript.ttf",
    "Pacifico": "Pacifico.ttf",
    "Lobster": "Lobster.ttf",
    "Caveat": "Caveat.ttf",
    "Pinyon Script": "PinyonScript.ttf",
    "Great Vibes": "GreatVibes.ttf",
    "Sacramento": "Sacramento.ttf",
    "Kaushan Script": "KaushanScript.ttf",
    "Oleo Script": "OleoScript.ttf",
    "Tangerine": "Tangerine.ttf",
}
