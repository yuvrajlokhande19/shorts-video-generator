"""ASS subtitle generation with style options (font, color, position, karaoke)."""


def hex_to_ass(hex_color):
    """#RRGGBB -> &HBBGGRR& (ASS uses BGR byte order)."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"&H{b:02X}{g:02X}{r:02X}&"


def _ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _karaoke_line(text, words, start=0.0, end=0.0):
    """Build a karaoke-timed line. Uses word boundaries if present, otherwise
    distributes the segment span proportionally across words by length."""
    tokens = text.split()
    if not tokens:
        return text
    if words:
        parts = []
        for w in words:
            cs = max(1, round((w["end"] - w["start"]) * 100))
            parts.append(f"{{\\k{cs}}}{w['word']}")
        return "".join(p + " " for p in parts).strip()
    span = max(0.1, end - start)
    total = sum(len(t) for t in tokens) or 1
    parts = []
    for t in tokens:
        cs = max(1, round(span * len(t) / total * 100))
        parts.append(f"{{\\k{cs}}}{t}")
    return "".join(p + " " for p in parts).strip()


def build_ass(timings, style, out_path):
    """timings: list of {"text","words","start","end"}.
    style: dict with font, size, color, outline, position, bold, box, highlight."""
    font = style.get("font", "Arial")
    size = int(style.get("size", 60))
    color = hex_to_ass(style.get("color", "#FFFFFF"))
    outline = hex_to_ass(style.get("outline", "#000000"))
    bold = "1" if style.get("bold", True) else "0"
    box = style.get("box", True)
    highlight = style.get("highlight", False)
    position = style.get("position", "bottom")  # bottom / center / top
    align = {"bottom": 2, "center": 5, "top": 8}.get(position, 2)

    border_style = "4" if box else "1"  # 4 = opaque box behind text
    back = "&H80000000" if box else "&H00000000"
    bord = "6" if box else "3"

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "WrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font},{size},{color},{color},{outline},{back},"
        f"{bold},0,0,0,100,100,0,0,{border_style},{bord},0,{align},60,60,90,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )

    events = []
    for seg in timings:
        start = _ass_time(seg["start"])
        end = _ass_time(seg["end"])
        text = _karaoke_line(seg["text"], seg["words"], seg["start"], seg["end"]) if highlight else seg["text"]
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events) + "\n")
    return out_path
