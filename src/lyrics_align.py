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


def generate_lyrics(theme, n=12, lang="hinglish"):
    """Generate original lyric lines for a theme via Gemini (free template fallback).

    lang: "english" | "hinglish" (Hindi in Latin script) | "hindi" (Devanagari).
    For Hindi songs, use "hinglish" so the sung words read naturally in Latin text.
    """
    if config.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.GEMINI_API_KEY)
            model = genai.GenerativeModel(config.GEMINI_MODEL)
            if lang == "hinglish":
                lang_note = (
                    "Write the lyrics in HINGLISH: Hindi written in the Latin/English "
                    "alphabet (e.g. 'Kaise ho', 'Dil mera', 'Tu hi hai meri zindagi', "
                    "'Raaton ko tanha'). Use common Hindi words transliterated. "
                    "Do NOT use Devanagari script."
                )
            elif lang == "hindi":
                lang_note = (
                    "Write the lyrics in Hindi using the Devanagari script only."
                )
            else:
                lang_note = "Write the lyrics in English."
            prompt = (
                f"Write original song lyrics for a short video (Instagram Reel / TikTok) "
                f"about: {theme}.\n{lang_note}\nReturn STRICT JSON only, no markdown: "
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
    return _template_lyrics(theme, lang)


def _template_lyrics(theme, lang="hinglish"):
    t = (theme or "this feeling").strip().title()
    if lang == "hindi":
        return [
            f"जब रात चुप है, तो तेरी याद आती है",
            "अँधेरे में तेरा नाम गूँजता है",
            "हम वो गाने थे जो दुनिया भूल गई",
            "बारिश में नाचा करते थे हम तन्हा",
            "पल को थाम ले पहले वो काला पड़े",
            "कहीं तारों को अब भी हमारी धुन याद है",
            "अगर इश्क़ एक शब्द है, तो सच लिख दे मुझे",
            "मैं धीरे से गाऊँगा, तन्हा चाँद में",
        ]
    if lang == "hinglish":
        return [
            f"Jab raat chup hai, tab teri yaad aati hai",
            "Andhere mein tera naam goonjta hai",
            "Hum wo gaane the jo duniya bhool gayi",
            "Barish mein naacha karte the hum tanha",
            "Pal ko thaam le pehle wo kaala pade",
            "Kahin taaron ko abhi bhi hamari dhun yaad hai",
            "Agar ishq ek lafz hai, toh sach likh de mujhe",
            "Main dheere se gaaunga, tanha chaand mein",
        ]
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
    if text and text.startswith("\ufeff"):
        text = text[1:]
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


def transcribe_lyrics(song_path, lang=None):
    """Extract the REAL sung lyrics from a song with word-level timestamps.

    Primary engine: faster-whisper (no torch needed) with lightweight
    vocal-isolation preprocessing. Falls back to the Vosk engine if
    faster-whisper is unavailable."""
    try:
        return _transcribe_fw(song_path, lang)
    except Exception as exc:
        print(f"[lyrics] faster-whisper failed ({exc}); trying Vosk.")
        try:
            return _transcribe_vosk(song_path, lang)
        except Exception as exc2:
            raise RuntimeError(f"lyric transcription failed: {exc2}")


def _lang_code(lang):
    return {"hinglish": "hi", "hindi": "hi", "english": "en", "hi": "hi", "en": "en"}.get(lang, "en")


def _group_words(words, gap=0.8, max_words=9):
    lines, cur = [], []
    for w in words:
        if cur and (w["start"] - cur[-1]["end"] > gap or len(cur) >= max_words):
            lines.append(_mkline(cur))
            cur = []
        cur.append(w)
    if cur:
        lines.append(_mkline(cur))
    return lines


def _mkline(ws):
    return {
        "text": " ".join(w["word"] for w in ws).strip(),
        "start": ws[0]["start"],
        "end": ws[-1]["end"],
        "words": ws,
    }


def _vocal_wav(song_path):
    """Preprocess a song to maximise speech recognition: drop to mono 16k and
    band-limit to the vocal range, reduce broadband music with a noise gate,
    then normalise. No GPU/torch needed."""
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp())
    wav = tmp / "vocals.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(song_path), "-vn",
         "-ac", "1", "-ar", "16000",
         "-af", "highpass=f=150,lowpass=f=4000,afftdn=nf=-22,"
                "dynaudnorm=f=150:g=12:p=0.8:m=100",
         str(wav)],
        check=True, capture_output=True,
    )
    return wav


_FW_MODEL = None
_FW_SIZE = None


def _load_fw(size="small"):
    global _FW_MODEL, _FW_SIZE
    from faster_whisper import WhisperModel

    if _FW_MODEL is None or _FW_SIZE != size:
        print(f"[lyrics] loading faster-whisper model '{size}' …")
        _FW_MODEL = WhisperModel(size, device="cpu", compute_type="int8")
        _FW_SIZE = size
    return _FW_MODEL


def _transcribe_fw(song_path, lang=None):
    wav = _vocal_wav(song_path)
    model = _load_fw("small")
    wlang = {"hi": "hi", "en": "en"}.get(_lang_code(lang))  # None -> auto-detect
    segs, _ = model.transcribe(
        str(wav), language=wlang, word_timestamps=True,
        vad_filter=True, condition_on_previous_text=False,
    )
    words = []
    for s in segs:
        for w in s.words:
            t = w.word.strip()
            if t:
                words.append({"word": t, "start": w.start, "end": w.end})
    if not words:
        raise RuntimeError("no speech detected by faster-whisper")
    # Re-group into multiple timed lines for nicer karaoke captions.
    return _group_words(words)



_VOSK_MODELS = {
    "hi": "vosk-model-small-hi-0.22",
    "en": "vosk-model-small-en-us-0.15",
}


def _vosk_model_dir(code):
    import tarfile
    import urllib.request
    import zipfile

    base = config.ASSETS_DIR / "vosk"
    base.mkdir(parents=True, exist_ok=True)
    name = _VOSK_MODELS.get(code, _VOSK_MODELS["en"])
    d = base / name
    if not (d / "conf" / "model.conf").exists():
        print(f"[vosk] downloading model {name} …")
        archive = None
        for ext, opener in ((".tar.gz", tarfile.open), (".zip", zipfile.ZipFile)):
            url = f"https://alphacephei.com/vosk/models/{name}{ext}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=240) as r:
                    archive = base / f"{name}{ext}"
                    with open(archive, "wb") as f:
                        f.write(r.read())
                break
            except Exception as exc:
                print(f"[vosk] {ext} download failed: {exc}")
        if not archive:
            raise RuntimeError(f"could not download Vosk model {name}")
        with opener(archive) as af:
            af.extractall(base)
    return str(d)


def _transcribe_vosk(song_path, lang=None):
    import json as _json
    import wave

    from vosk import KaldiRecognizer, Model

    code = _lang_code(lang)
    model_path = _vosk_model_dir(code)
    wav = _vocal_wav(song_path)
    model = Model(model_path)
    wf = wave.open(str(wav), "rb")
    rec = KaldiRecognizer(model, wf.getframerate())
    words = []
    last_partial = ""
    while True:
        data = wf.readframes(4000)
        if not data:
            break
        if rec.AcceptWaveform(data):
            for w in _json.loads(rec.Result()).get("result", []):
                words.append({"word": w["word"], "start": w["start"], "end": w["end"]})
        else:
            p = _json.loads(rec.PartialResult()).get("partial", "")
            if p:
                last_partial = p
    final = _json.loads(rec.FinalResult())
    for w in final.get("result", []):
        words.append({"word": w["word"], "start": w["start"], "end": w["end"]})
    wf.close()

    if words:
        return _group_words(words)

    # No word-level timings (very short audio): use the transcript text,
    # split into lines and distributed evenly across the duration.
    text = (final.get("text") or last_partial).strip()
    if not text:
        raise RuntimeError("no speech detected by Vosk")
    dur = song_duration(song_path)
    toks = text.split()
    if not toks:
        raise RuntimeError("no speech detected by Vosk")
    step = dur / len(toks)
    chunk = 7
    lines = []
    for i in range(0, len(toks), chunk):
        seg = toks[i:i + chunk]
        s = i * step
        e = min((i + len(seg)) * step, dur)
        wps = (e - s) / len(seg) if seg else step
        lines.append({
            "text": " ".join(seg),
            "start": s,
            "end": e,
            "words": [{"word": t, "start": s + j * wps, "end": s + (j + 1) * wps}
                      for j, t in enumerate(seg)],
        })
    return lines


def romanize_lines(lines):
    """Convert Devanagari lyric lines to Hinglish (Latin) when possible."""
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate
    except Exception:
        return lines  # keep Devanagari if the lib is missing
    out = []
    for ln in lines:
        try:
            ln = dict(ln)
            ln["text"] = transliterate(ln["text"], sanscript.DEVANAGARI, sanscript.OPTITRANS)
            if ln.get("words"):
                ln["words"] = [dict(w, word=transliterate(w["word"], sanscript.DEVANAGARI, sanscript.OPTITRANS)) for w in ln["words"]]
        except Exception:
            pass
        out.append(ln)
    return out
