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
