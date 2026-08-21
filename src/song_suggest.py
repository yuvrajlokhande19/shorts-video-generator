"""Free / no-copyright song suggestions for Lyric Reels.

Without any API key we return a curated list of well-known free-music sources
(the user downloads a track and uploads it). If a Pixabay API key is set
(PIXABAY_API_KEY, free), we query Pixabay Music and return direct preview URLs.
"""
import json
import urllib.parse
import urllib.request

import config

CURATED = [
    {"title": "YouTube Audio Library", "artist": "free, cleared for Shorts/Reels",
     "url": "https://studio.youtube.com/channel/UC.../music", "license": "YouTube Audio Library"},
    {"title": "Pixabay Music", "artist": "community, royalty-free",
     "url": "https://pixabay.com/music/", "license": "Pixabay License (free)"},
    {"title": "Mixkit", "artist": "free stock music",
     "url": "https://mixkit.co/free-stock-music/", "license": "Mixkit License"},
    {"title": "Free Music Archive", "artist": "various CC licenses",
     "url": "https://freemusicarchive.org/", "license": "CC / various"},
    {"title": "Uppbeat", "artist": "free with account",
     "url": "https://uppbeat.io/", "license": "Uppbeat (free tier)"},
    {"title": "Incompetech (Kevin MacLeod)", "artist": "Kevin MacLeod",
     "url": "https://incompetech.com/music/royalty-free/", "license": "CC BY"},
]


def suggest(query=None):
    if config.PIXABAY_API_KEY:
        try:
            q = urllib.parse.quote(query or "lofi")
            url = (f"https://pixabay.com/api/?key={config.PIXABAY_API_KEY}"
                   f"&q={q}&media_type=music&per_page=10")
            with urllib.request.urlopen(url, timeout=30) as r:
                data = json.loads(r.read())
            out = []
            for h in data.get("hits", []):
                out.append({
                    "title": h.get("name", "track"),
                    "artist": h.get("artist", ""),
                    "url": h.get("url") or h.get("fullUrl"),
                    "license": "Pixabay License",
                })
            if out:
                return out
        except Exception as exc:
            print(f"[songs] Pixabay failed: {exc}")
    return CURATED
