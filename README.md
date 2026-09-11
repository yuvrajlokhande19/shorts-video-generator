# 🎬 Auto Shorts — AI Video Studio + Movie-to-Reels Splitter

A complete video creation suite with **three powerful modes**:
1. **AI Short Generator** — Turn topics into scripted shorts with TTS narration
2. **Lyric Reel Creator** — Transform songs into synced karaoke-style lyric videos  
3. **Movie-to-Reels Splitter** ⭐ NEW — Split movies into 30-second portrait reels with text overlays

Built with **Python + Flask** and a modern vanilla-JS web UI.

---

## ✨ Features

### 🎞️ Movie-to-Reels Splitter (NEW)
- **Upload any movie/video** (MP4, MKV, AVI, MOV, WebM up to 2GB)
- **Auto-split into 30-second segments** in 9:16 portrait format (perfect for Reels/Shorts/TikTok)
- **Smart last-segment handling** — pads final segment to full 30s by looping if needed
- **Text overlays on every reel:**
  - Movie title (customizable position: top, bottom, corners, center)
  - Part number (e.g., "Part 1 of 12", "Part 2 of 12", etc.)
- **Full style control:** 30+ fonts (including Hindi/Devanagari support), colors, outlines, sizes
- **Live preview canvas** — see exactly how text overlays will look before generating
- **Auto-fetch movie metadata** from TMDB/OMDB (title, year, genres, runtime, poster)
- **Extracts clean title from filename** if no API keys configured
- **Download individual reels or all as ZIP**

### 🤖 AI Short Generator
- **AI script generation** via Google Gemini (with free template fallback)
- **Free text-to-speech** using `edge-tts` (Indian voices, Hinglish/Hindi/English)
- **Stock footage** from Pexels/Pixabay or procedural gradients
- **Burned-in subtitles** with customizable style (font, size, color, outline, position, box, karaoke highlight)
- **Background music** — auto ambient or upload your own
- **Output:** 1080×1920 (vertical) or 1920×1080 (horizontal), 30 fps

### 🎵 Lyric Reel Creator
- **Auto mode:** Drop a song → app transcribes *real* vocals via faster-whisper/Vosk → auto-syncs lyrics
- **Languages:** Hinglish, Hindi (Devanagari), English
- **Background:** Upload image, stock search, AI image (Gemini), or procedural gradient
- **Style:** 10+ handwriting fonts, karaoke highlight, Ken Burns motion
- **Edit & re-render** without re-uploading song

---

## 🚀 Setup

> Requires **Python 3.11+** and **ffmpeg** on your `PATH`.

```bash
# 1. Open the project
cd auto-shorts

# 2. Create a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1        # Windows
# source venv/bin/activate         # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) add API keys
copy .env.example .env
#   edit .env and set GEMINI_API_KEY, PEXELS_API_KEY, PIXABAY_API_KEY
#   TMDB_API_KEY, OMDB_API_KEY (for movie metadata)
#   (all optional — the app runs fully free without them)

# 5. Run it
python app.py
```

Open <http://127.0.0.1:5000> in your browser.

### One-click launcher (no terminal)
`start.vbs` launches the server hidden and opens your browser automatically.
Create a Desktop shortcut:
```powershell
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\Auto Shorts.lnk")
$lnk.TargetPath = "$PWD\start.vbs"; $lnk.WorkingDirectory = "$PWD"; $lnk.Save()
```

---

## 🔑 API Keys (All Optional)

| Feature | Key | Get it free at |
|---------|-----|----------------|
| AI Scripts | `GEMINI_API_KEY` | <https://aistudio.google.com/apikey> |
| Stock Video | `PEXELS_API_KEY` | <https://www.pexels.com/api/> |
| Stock Video | `PIXABAY_API_KEY` | <https://pixabay.com/api/docs/> |
| Movie Metadata | `TMDB_API_KEY` | <https://www.themoviedb.org/settings/api> |
| Movie Metadata | `OMDB_API_KEY` | <http://www.omdbapi.com/apikey.aspx> |

**Without keys:** App uses templates, procedural backgrounds, and filename extraction — completely free.

---

## 🎞️ Movie-to-Reels Splitter — Detailed Guide

### Quick Start
1. Click **"Movie to Reels"** tab (selected by default)
2. **Drag & drop** a movie file or click to browse
3. Enter **Movie Name** (auto-filled from filename)
4. Click **"Auto-fetch Movie Info"** (optional, needs TMDB/OMDB key)
5. Adjust **Text Overlay** settings (font, color, position)
6. Click **"Generate Reels"**

### Settings Explained

| Setting | Description | Default |
|---------|-------------|---------|
| Segment Duration | Length of each reel in seconds | 30s |
| Pad Last Segment | Loop final segment to reach full duration | ✅ Enabled |
| Background | Color for letterboxing (black/white/blurred) | Black |
| Font | 30+ fonts including Poppins, Noto Sans Devanagari, Hind | Poppins |
| Font Size | Text size in pixels | 56 |
| Text Color | Main text color | White |
| Outline Color | Text stroke color | Black |
| Movie Name Position | Where to show movie title | Top |
| Part Number Position | Where to show "Part X of Y" | Bottom Right |

### Text Position Options
- **Top** / **Bottom** / **Center**
- **Top Left** / **Top Right** / **Bottom Left** / **Bottom Right**

### Last Segment Handling
If your movie is 2h 15m 30s (8130s) with 30s segments:
- Segments 1-270: 30s each (8100s)
- Segment 271: 30s (padded from 30s remaining) ✅

If movie is 2h 15m 10s (8110s):
- Segments 1-270: 30s each (8100s)
- Segment 271: 10s → **padded to 30s by looping** ✅

---

## 🗂️ Project Layout

```
auto-shorts/
├── app.py                 # Flask server + SSE progress API (3 modes)
├── config.py              # Paths, settings, fonts, splitter defaults
├── src/
│   ├── script_gen.py      # AI script generation (Gemini + fallback)
│   ├── tts.py             # edge-tts narration
│   ├── stock.py           # Pexels/Pixabay or procedural clips
│   ├── subtitles.py       # ASS subtitle styling (AI Shorts)
│   ├── music.py           # Ambient synth / local music
│   ├── video_builder.py   # FFmpeg assembly (AI Shorts)
│   ├── lyrics_align.py    # LRC/SRT parsing + auto-sync (Lyric Reels)
│   ├── image_source.py    # Upload / stock / AI / procedural images
│   ├── lyric_renderer.py  # ASS karaoke + Ken Burns + FFmpeg (Lyric Reels)
│   ├── song_suggest.py    # Free song suggestions
│   ├── video_splitter.py  # ⭐ Movie-to-Reels splitting logic
│   └── movie_metadata.py  # ⭐ TMDB/OMDB metadata fetching
├── fonts/                 # Bundled TTF fonts (handwriting + system)
├── static/                # Web UI (index.html, app.js, style.css)
├── assets/                # User clips/ & music/
├── movies/                # Uploaded movies (temp)
├── output/                # Generated videos (gitignored)
├── temp/                  # Temporary processing files
└── samples/               # Example outputs
```

---

## 🔧 How the Movie Splitter Works

1. **Analyze** — FFprobe gets duration, resolution, codec
2. **Calculate** — Split into N × 30s segments (last padded if needed)
3. **Process each segment:**
   - Trim to exact time range
   - Scale & crop to 1080×1920 (9:16 portrait, center crop)
   - Burn text overlays via FFmpeg `drawtext` filter:
     - Movie name at chosen position
     - "Part X of Y" at chosen position
   - Pad last segment by looping if shorter than 30s
4. **Encode** — H.264, CRF 20, AAC 128kbps, yuv420p
5. **Output** — MP4 files in `output/` directory

---

## ⚠️ Notes

- **FFmpeg required** on PATH (test with `ffmpeg -version`)
- **Production:** Use `gunicorn` instead of Flask dev server
- **GPU:** Not required; all processing is CPU-based
- **Memory:** Large movies (>2GB) may need more RAM
- **Hindi/Devanagari:** Fonts like "Noto Sans Devanagari" and "Hind" included for proper rendering

---

## 📦 Sample Outputs

- `samples/sample_vertical.mp4` — 9:16 AI Short
- `samples/sample_horizontal.mp4` — 16:9 AI Short  
- `samples/sample_lyric.mp4` — Lyric Reel with karaoke sync
- `samples/sample_splitter.mp4` — Movie Reel with text overlays

---

## 🙏 Credits

- **Fonts:** Google Fonts (Poppins, Righteous, Noto, Hind, etc.)
- **Icons:** Heroicons / Lucide (SVG)
- **TTS:** Microsoft Edge TTS (`edge-tts`)
- **Speech:** faster-whisper / Vosk
- **Video:** FFmpeg