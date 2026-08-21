"""Final video assembly with ffmpeg: cover-scale clips, burn-in ASS subtitles,
and mixed narration + background music."""
import subprocess
from pathlib import Path


def build(workdir, clip_paths, narration_wav, ass_path, music_path,
          w, h, out_path, music_vol):
    """clip_paths: list of (path, duration)."""
    list_path = workdir / "concat.txt"
    with open(list_path, "w") as f:
        for cp, dur in clip_paths:
            f.write(f"file '{Path(cp).name}'\n")
            f.write(f"duration {dur:.3f}\n")

    bg = workdir / "bg.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
         "-c", "copy", str(bg)],
        check=True, cwd=workdir, capture_output=True,
    )

    filt = (
        f"[0:v]scale=iw*max({w}/iw\\,{h}/ih):ih*max({w}/iw\\,{h}/ih)[s];"
        f"[s]crop={w}:{h}[c];[c]setsar=1[p];"
        f"[p]subtitles={Path(ass_path).name.replace(chr(92), '/')}[v];"
        f"[1:a]volume=1.0[na];[2:a]volume={music_vol:.3f}[ma];"
        f"[na][ma]amix=inputs=2:duration=first:dropout_transition=0[a]"
    )

    subprocess.run(
        ["ffmpeg", "-y", "-i", str(bg), "-i", str(narration_wav),
         "-i", str(music_path), "-filter_complex", filt,
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264",
         "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(out_path)],
        check=True, cwd=workdir, capture_output=True,
    )
    return out_path
