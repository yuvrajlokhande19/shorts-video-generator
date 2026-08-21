"""Lyric parsing & timing for the Lyric Reel mode.

Supports:
  - .lrc  (timestamped lines, exact sync)
  - .srt  (timestamped lines, exact sync)
  - plain text (no timestamps -> distributed, or auto-aligned via whisper)
The normalized output is a list of lines, each with start/end seconds and
optional per-word timings for karaoke highlighting.
"""
import re
import subprocess
import tempfile
from pathlib import Path

import config


def _hms_to_sec(s):
    s = s.strip()
    if "," in s:
        s = s.replace(",", ".")
    parts = s.split(":")
    parts = [float(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, sec = parts
    return h * 3600 + m * 60 + sec


def _split_words(text):
    return [w for w in re.split(r"(\s+)", text) if w.strip()]


def _distribute_words(text, start, end):
    """Split a line's span across its words proportionally to length."""
    tokens = _split_words(text)
    words = [w for w in tokens if w.strip()]
    if not words:
        return []
    total = sum(len(w) for w in words) or 1
    spans = []
    t = start
    for w in words:
        dur = (end - start) * len(w) / total
        spans.append({"word": w, "start": t, "end": t + dur})
        t += dur
    return spans


def parse_lrc(text):
    lines = []
    pending = None
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        stamps = re.findall(r"\[(\d+):(\d+(?:\.\d+)?)\]", raw)
        if not stamps:
            continue
        lyric = re.sub(r"\[[^\]]*\]", "", raw).strip()
        if not lyric:
            continue
        for mm, ss in stamps:
            start = int(mm) * 60 + float(ss)
            lines.append({"text": lyric, "start": start, "end": None, "words": None})
    lines.sort(key=lambda l: l["start"])
    for i, ln in enumerate(lines):
        ln["end"] = lines[i + 1]["start"] if i + 1 < len(lines) else ln["start"] + 3.0
        ln["words"] = _distribute_words(ln["text"], ln["start"], ln["end"])
    return lines


def parse_srt(text):
    lines = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        parts = block.strip().split("\n")
        if len(parts) < 2:
            continue
        m = re.search(r"(\d+:\d+:\d+[,.]\d+)\s*-->\s*(\d+:\d+:\d+[,.]\d+)", block)
        if not m:
            continue
        start = _hms_to_sec(m.group(1))
        end = _hms_to_sec(m.group(2))
        lyric = " ".join(parts[2:]).strip()
        if not lyric:
            continue
        lines.append(
            {
                "text": lyric,
                "start": start,
                "end": end,
                "words": _distribute_words(lyric, start, end),
            }
        )
    lines.sort(key=lambda l: l["start"])
    return lines


def parse_plain(text):
    lines = []
    for raw in text.splitlines():
        raw = raw.strip()
        if raw:
            lines.append({"text": raw, "start": None, "end": None, "words": None})
    return lines


def finalize_timings(lines, total_duration):
    """Fill missing line/word timings by distributing across the song."""
    if not lines:
        return lines
    # If no line has timing, distribute all lines across the song.
    if all(ln["start"] is None for ln in lines):
        total_words = sum(len(_split_words(ln["text"])) for ln in lines) or 1
        t = 0.0
        for ln in lines:
            wc = len(_split_words(ln["text"]))
            dur = total_duration * wc / total_words
            ln["start"] = t
            ln["end"] = t + dur
            t += dur
    # Ensure each line has word timings.
    for ln in lines:
        if ln["words"] is None and ln["start"] is not None and ln["end"] is not None:
            ln["words"] = _distribute_words(ln["text"], ln["start"], ln["end"])
    return lines


def detect_format(filename, text):
    if filename:
        ext = Path(filename).suffix.lower()
        if ext == ".lrc":
            return "lrc"
        if ext == ".srt":
            return "srt"
    if re.search(r"\[\d+:\d+", text) and re.search(r"-->", text) is None:
        return "lrc"
    if "-->" in text:
        return "srt"
    return "txt"


def generate_lyrics(theme, n=12):
    """Generate original lyric lines for a theme via Gemini (free template fallback)."""
    if config.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.GEMINI_API_KEY)
            model = genai.GenerativeModel(config.GEMINI_MODEL)
            prompt = (
                f"Write original song lyrics for a short video (Instagram Reel / TikTok) "
                f"about: {theme}.\nReturn STRICT JSON only, no markdown: "
                f'{{"lines": [string, ...]}} with about {n} short lines '
                f"(max 8 words each), emotional and rhythmic, one line per caption."
            )
            resp = model.generate_content(prompt)
            text = re.sub(r"```json|```", "", resp.text).strip()
            data = json.loads(text)
            lines = [str(l).strip() for l in data.get("lines", []) if str(l).strip()]
            if lines:
                return lines
        except Exception as exc:
            print(f"[lyrics] Gemini generation failed ({exc}); using template.")
    return _template_lyrics(theme)


def _template_lyrics(theme):
    t = (theme or "this feeling").strip().title()
    return [
        f"When the night is quiet, I think of {t}",
        "Every echo in the dark sounds like your name",
        "We were a song that the world forgot to play",
        "Dancing in the rain with no one to save",
        "Hold the moment before it turns to grey",
        "Somewhere the stars still remember our tune",
        "If love is a lyric, then write me the truth",
        "And I will sing it softly, alone in the moon",
    ]


def parse_lyrics(text, filename=None):
    fmt = detect_format(filename, text)
    if fmt == "lrc":
        return parse_lrc(text)
    if fmt == "srt":
        return parse_srt(text)
    return parse_plain(text)


def song_duration(song_path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(song_path)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except Exception:
        return 30.0


def auto_align(lines, song_path):
    """Optional: align plain lyrics to the song via demucs + faster-whisper.
    Requires: pip install demucs faster-whisper. Returns lines with timings."""
    import tempfile
    from pathlib import Path

    try:
        import torch  # noqa: F401
        from demucs.apply import apply_model, load_model
        from demucs.pretrained import get_model
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise RuntimeError(
            "Auto-sync needs 'demucs' and 'faster-whisper' "
            f"(pip install demucs faster-whisper). Missing: {exc}"
        )

    tmp = Path(tempfile.mkdtemp())
    # 1. isolate vocals
    model = get_model("htdemucs")
    apply_model(model, song_path, tmp / "vocals", device="cpu")
    vocal = tmp / "vocals" / "vocals.wav"
    # 2. transcribe vocals (word-level)
    wmodel = WhisperModel("base", device="cpu", compute_type="int8")
    segs, _ = wmodel.transcribe(str(vocal), word_timestamps=True)
    transcript = []
    for s in segs:
        for w in s.words:
            transcript.append((w.word, w.start, w.end))
    # 3. fuzzy-align each lyric line to a transcript window
    # (simple greedy match on normalized tokens)
    norm = lambda t: re.sub(r"[^a-z0-9 ]", "", t.lower())
    t_words = [norm(w[0]) for w in transcript]
    idx = 0
    for ln in lines:
        toks = [t for t in norm(ln["text"]).split() if t]
        if not toks:
            ln["start"] = ln["end"] = 0
            continue
        # find best starting position
        best, best_score = idx, -1
        for j in range(idx, max(idx, len(t_words) - len(toks) + 1)):
            score = sum(1 for k in range(len(toks))
                        if t_words[j + k] == toks[k]) if j + len(toks) <= len(t_words) else 0
            if score > best_score:
                best_score, best = score, j
        end_j = min(best + len(toks), len(transcript))
        if best < len(transcript):
            ln["start"] = transcript[best][1]
            ln["end"] = transcript[end_j - 1][2] if end_j > best else transcript[best][2] + 2
            ln["words"] = [
                {"word": transcript[k][0], "start": transcript[k][1], "end": transcript[k][2]}
                for k in range(best, end_j)
            ]
        idx = max(idx, end_j)
    return lines
