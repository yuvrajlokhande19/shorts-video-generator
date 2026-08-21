"""Background music: use a user-supplied track from assets/music/ if present,
otherwise synthesize a free ambient pad with numpy (no API key required)."""
import os
import random
import subprocess
import wave

import numpy as np

import config


def _local_music():
    files = []
    for ext in ("*.mp3", "*.wav", "*.ogg", "*.m4a"):
        files.extend(config.MUSIC_DIR.glob(ext))
    return sorted(files)


def _synthesize_ambient(duration, out_path, seed=7):
    sr = 44100
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    rng = np.random.default_rng(seed)

    chords = [
        [261.63, 329.63, 392.00],  # C major
        [293.66, 349.23, 440.00],  # D minor
        [220.00, 261.63, 329.63],  # A minor
        [196.00, 246.94, 293.66],  # G major
    ]
    seg = duration / len(chords)
    sig = np.zeros(n)
    for i, chord in enumerate(chords):
        s = int(i * seg * sr)
        e = int((i + 1) * seg * sr)
        tt = t[s:e] - t[s]
        for f in chord:
            vib = 1 + 0.0025 * np.sin(2 * np.pi * 4.5 * tt)
            sig[s:e] += np.sin(2 * np.pi * f * vib * tt) * 0.16
            sig[s:e] += np.sin(2 * np.pi * f * 2 * tt) * 0.05
        fade = int(0.6 * sr)
        env = np.ones_like(tt)
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        sig[s:e] *= env

    # gentle lowpass via moving average
    sig = np.convolve(sig, np.ones(24) / 24, mode="same")
    sig /= np.max(np.abs(sig)) + 1e-9
    sig *= 0.28
    sig = (sig * 32767).astype(np.int16)

    with wave.open(str(out_path), "wb") as wv:
        wv.setnchannels(1)
        wv.setsampwidth(2)
        wv.setframerate(sr)
        wv.writeframes(sig.tobytes())
    return out_path


def get_music(duration, workdir, override=None):
    """Return a path to a music file ~`duration` seconds long.
    If `override` (a user-uploaded audio path) is given, loop it."""
    if override:
        out = workdir / "music.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(override),
             "-t", f"{duration:.2f}", "-c:a", "pcm_s16le", str(out)],
            check=True, capture_output=True,
        )
        return out
    local = _local_music()
    if local:
        src = random.choice(local)
        out = workdir / "music.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
             "-t", f"{duration:.2f}", "-c:a", "pcm_s16le", str(out)],
            check=True, capture_output=True,
        )
        return out
    out = workdir / "music.wav"
    return _synthesize_ambient(duration, out)
