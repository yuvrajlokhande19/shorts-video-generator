"""Render a Lyric Reel: static/AI/stock image + Ken Burns + karaoke ASS
subtitles + the song, into an HD MP4."""
import os
import subprocess
from pathlib import Path

import config


def _ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _hex_to_ass(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"&H{b:02X}{g:02X}{r:02X}&"


def _karaoke(words):
    if not words:
        return ""
    parts = []
    for w in words:
        cs = max(1, round((w["end"] - w["start"]) * 100))
        parts.append(f"{{\\k{cs}}}{w['word']}")
    return "".join(p + " " for p in parts).strip()


def build_ass(lines, style, w, h, out_path):
    font = style.get("font", "Dancing Script")
    size = int(style.get("size", 72))
    highlight = _hex_to_ass(style.get("highlight_color", "#ff5ca8"))
    text_col = _hex_to_ass(style.get("text_color", "#ffffff"))
    outline = _hex_to_ass(style.get("outline_color", "#000000"))
    bold = "1" if style.get("bold", True) else "0"
    box = style.get("box", False)
    position = style.get("position", "center")
    preview = style.get("preview", True)

    border_style = "4" if box else "1"
    back = "&H80000000" if box else "&H00000000"
    bord = "5"

    # vertical placement in ASS coordinate space (PlayResX/Y = w,h)
    cx = w / 2
    cy = {"top": h * 0.27, "bottom": h * 0.76, "center": h * 0.47}.get(position, h * 0.47)
    py = h * 0.62

    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Lyric,{font},{size},{highlight},{text_col},{outline},{back},"
        f"{bold},0,0,0,100,100,0,0,{border_style},{bord},0,5,60,60,90,1\n"
        f"Style: Next,{font},{int(size*0.6)},{text_col},{text_col},{outline},{back},"
        f"{bold},0,0,0,100,100,0,0,{border_style},3,0,5,60,60,90,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )

    events = []
    for i, ln in enumerate(lines):
        start = _ass_time(ln["start"])
        end = _ass_time(ln["end"])
        karaoke = _karaoke(ln["words"]) if ln.get("words") else ln["text"]
        events.append(
            f"Dialogue: 0,{start},{end},Lyric,,0,0,0,,"
            f"{{\\an5\\pos({cx:.0f},{cy:.0f})}}{karaoke}"
        )
        if preview and i + 1 < len(lines):
            nxt = lines[i + 1]
            pstart = _ass_time(max(0.0, ln["start"] - 2.4))
            pend = _ass_time(ln["start"])
            events.append(
                f"Dialogue: 0,{pstart},{pend},Next,,0,0,0,,"
                f"{{\\an5\\pos({cx:.0f},{py:.0f})}}{nxt['text']}"
            )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events) + "\n")
    return out_path


def render(image_path, song_path, ass_path, w, h, out_path, duration,
           kenburns=True):
    image_path = str(Path(image_path).resolve())
    song_path = str(Path(song_path).resolve())
    out_path = str(Path(out_path).resolve())
    # relative fonts path (avoids Windows drive-colon breaking the filter parser)
    work = Path(ass_path).parent
    fonts_dir = os.path.relpath(config.FONTS_DIR, work).replace("\\", "/")
    ass_name = Path(ass_path).name

    filt = (
        f"[0:v]scale=iw*max({w}/iw\\,{h}/ih):ih*max({w}/iw\\,{h}/ih)[s];"
        f"[s]crop={w}:{h}[s0]"
    )
    if kenburns:
        filt += (
            f";[s0]zoompan=z='min(1.0+0.00035*on,1.18)':d=1:s={w}x{h}:fps=30,"
            f"setsar=1[v]"
        )
    else:
        filt += ";[s0]setsar=1[v]"
    filt += f";[v]subtitles={ass_name}:fontsdir={fonts_dir}[vout]"

    subprocess.run(
        ["ffmpeg", "-y", "-framerate", "30", "-loop", "1", "-i", str(image_path),
         "-i", str(song_path), "-filter_complex", filt,
         "-map", "[vout]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", "-t", f"{duration:.2f}", str(out_path)],
        check=True, cwd=Path(ass_path).parent, capture_output=True,
    )
    return out_path
