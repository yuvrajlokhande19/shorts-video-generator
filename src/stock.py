"""Stock footage: optional Pexels/Pixabay (free with key), else free procedural
background clips, else user-supplied clips in assets/clips/."""
import json
import subprocess
import urllib.parse
import urllib.request

import config

# Gradient color pairs (hex, no '#') used for procedural backgrounds.
GRADIENTS = config.GRADIENTS


def _local_clips():
    files = []
    for ext in ("*.mp4", "*.mov", "*.webm"):
        files.extend(config.CLIPS_DIR.glob(ext))
    return sorted(files)


def _make_gradient_clip(out_path, w, h, duration, pair_index):
    c0, c1 = GRADIENTS[pair_index % len(GRADIENTS)]
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"gradients=s={w}x{h}:c0={c0}:c1={c1}:x0=0:y0=0:x1={w}:y1={h}",
            "-t", f"{duration:.3f}", "-r", "30",
            "-vf", f"zoompan=z='min(zoom+0.0006,1.05)':d=1:s={w}x{h}:fps=30,format=yuv420p",
            str(out_path),
        ],
        check=True, capture_output=True,
    )


def _download(url, out_path):
    req = urllib.request.Request(url, headers={"User-Agent": "auto-shorts/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r, open(out_path, "wb") as f:
        f.write(r.read())


def _pexels(topic, count):
    if not config.PEXELS_API_KEY:
        return []
    try:
        url = ("https://api.pexels.com/videos/search?query="
               + urllib.parse.quote(topic) + f"&per_page={count}&orientation=vertical")
        req = urllib.request.Request(url, headers={"Authorization": config.PEXELS_API_KEY})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        out = []
        for v in data.get("videos", []):
            files = v.get("video_files", [])
            if not files:
                continue
            files.sort(key=lambda f: f.get("width", 0), reverse=True)
            out.append(files[0]["link"])
            if len(out) >= count:
                break
        return out
    except Exception as exc:
        print(f"[stock] Pexels failed: {exc}")
        return []


def get_clips(topic, timings, w, h, workdir):
    """Return list of (clip_path, duration) aligned to each timing segment."""
    durations = [max(1.0, t["duration"]) for t in timings]
    local = _local_clips()
    remote = _pexels(topic, len(durations)) if not local else []

    paths = []
    for i, dur in enumerate(durations):
        out = workdir / f"clip_{i:03d}.mp4"
        if local:
            src = local[i % len(local)]
            # reuse local clip, trimmed/looped to required duration
            subprocess.run(
                ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
                 "-t", f"{dur:.3f}", "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1",
                 "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                 str(out)],
                check=True, capture_output=True,
            )
        elif remote:
            try:
                _download(remote[i % len(remote)], out)
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(out),
                     "-t", f"{dur:.3f}", "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1",
                     "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                     str(out)],
                    check=True, capture_output=True,
                )
            except Exception:
                _make_gradient_clip(out, w, h, dur, i)
        else:
            _make_gradient_clip(out, w, h, dur, i)
        paths.append((out, dur))
    return paths
