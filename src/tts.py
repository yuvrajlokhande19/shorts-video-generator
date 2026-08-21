"""Text-to-speech using edge-tts (free, no API key, word-level timings)."""
import asyncio
import io

import edge_tts
from pydub import AudioSegment

# Friendly label -> edge-tts voice id
VOICES = {
    "Aria (US, Female)": "en-US-AriaNeural",
    "Guy (US, Male)": "en-US-GuyNeural",
    "Jenny (US, Female)": "en-US-JennyNeural",
    "Christopher (US, Male, warm)": "en-US-ChristopherNeural",
    "Sonia (UK, Female)": "en-GB-SoniaNeural",
    "Ryan (UK, Male)": "en-GB-RyanNeural",
    "Natasha (AU, Female)": "en-AU-NatashaNeural",
    "William (AU, Male)": "en-AU-WilliamNeural",
}

VOICE_LIST = [{"label": k, "id": v} for k, v in VOICES.items()]


async def _synth_sentence(text, voice):
    communicate = edge_tts.Communicate(text, voice)
    boundary = None  # SentenceBoundary: offsets in 100-nanosecond ticks
    audio_chunks = []
    async for event in communicate.stream():
        if event["type"] == "audio":
            audio_chunks.append(event["data"])
        elif event["type"] == "SentenceBoundary":
            boundary = {
                "start": event["offset"] / 10_000_000,
                "end": (event["offset"] + event["duration"]) / 10_000_000,
            }
    return b"".join(audio_chunks), boundary


def synthesize(segments, voice_id):
    """segments: list of {"text": str}.
    Returns (AudioSegment full narration, list of per-segment timing dicts)."""
    full = AudioSegment.empty()
    timings = []
    offset = 0.0
    for seg in segments:
        audio_bytes, boundary = asyncio.run(_synth_sentence(seg["text"], voice_id))
        seg_audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        dur = len(seg_audio) / 1000.0
        # Prefer SentenceBoundary timing when available for tighter sync.
        if boundary:
            start = offset + boundary["start"]
            end = offset + boundary["end"]
        else:
            start = offset
            end = offset + dur
        timings.append(
            {
                "text": seg["text"],
                "words": [],
                "start": start,
                "end": end,
                "duration": dur,
            }
        )
        full += seg_audio
        offset += dur
    if not timings:
        raise RuntimeError("TTS produced no audio")
    return full, timings
