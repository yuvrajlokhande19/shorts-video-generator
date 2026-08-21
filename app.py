import json
import time
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file, send_from_directory

import config
import src.script_gen as script_gen
import src.tts as tts
import src.stock as stock
import src.subtitles as subtitles
import src.music as music
import src.video_builder as video_builder
import src.lyrics_align as lyrics_align
import src.image_source as image_source
import src.lyric_renderer as lyric_renderer
import src.song_suggest as song_suggest

app = Flask(__name__, static_folder=None)


def _ev(kind, message, **extra):
    payload = {"type": kind, "message": message, **extra}
    return f"data: {json.dumps(payload)}\n\n"


def run_pipeline(opts):
    topic = opts["topic"].strip()
    orientation = opts.get("orientation", "vertical")
    if orientation not in config.RESOLUTIONS:
        orientation = "vertical"
    w, h = config.RESOLUTIONS[orientation]

    voice_id = opts.get("voice", "en-US-AriaNeural")
    use_ai = bool(opts.get("use_ai", True))
    music_vol = max(0.0, min(1.0, float(opts.get("music_volume", 35)) / 100.0))

    style = opts.get("subtitle_style", {})

    job_id = uuid.uuid4().hex[:8]
    workdir = config.TEMP_DIR / job_id
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        yield _ev("progress", "Generating script…")
        script = script_gen.generate_script(topic, target_duration=45, use_ai=use_ai)
        segments = [{"text": s} for s in script["segments"]]
        if not segments:
            yield _ev("error", "No script segments produced.")
            return

        yield _ev("progress", "Synthesizing voiceover…", title=script.get("title"))
        narration, timings = tts.synthesize(segments, voice_id)
        narration_wav = workdir / "narration.wav"
        narration.export(narration_wav, format="wav")
        total_dur = sum(t["duration"] for t in timings)

        yield _ev("progress", "Preparing background footage…")
        clip_paths = stock.get_clips(topic, timings, w, h, workdir,
                                     local_images=opts.get("local_images"))

        yield _ev("progress", "Building subtitles…")
        ass_path = workdir / "subs.ass"
        subtitles.build_ass(timings, style, ass_path)

        yield _ev("progress", "Adding background music…")
        music_path = music.get_music(total_dur, workdir,
                                     override=opts.get("bg_song_path"))

        yield _ev("progress", "Rendering video…")
        out_name = f"{job_id}_{orientation}.mp4"
        out_path = config.OUTPUT_DIR / out_name
        video_builder.build(workdir, clip_paths, narration_wav, ass_path,
                            music_path, w, h, out_path, music_vol)

        yield _ev("done", "Video ready!", url=f"/output/{out_name}",
                  title=script.get("title"), duration=round(total_dur, 1))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        yield _ev("error", f"Failed: {exc}")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:p>")
def static_files(p):
    return send_from_directory("static", p)


@app.route("/api/voices")
def api_voices():
    return jsonify(tts.VOICE_LIST)


@app.route("/api/fonts")
def api_fonts():
    return jsonify(list(config.FONTS.keys()))


@app.route("/api/songs")
def api_songs():
    return jsonify(song_suggest.suggest(request.args.get("query")))


@app.route("/api/images/search", methods=["POST"])
def api_image_search():
    data = request.get_json(force=True, silent=True) or {}
    query = data.get("query", "")
    return jsonify({"images": image_source.search_images(query)})


@app.route("/api/images/generate", methods=["POST"])
def api_image_generate():
    data = request.get_json(force=True, silent=True) or {}
    prompt = data.get("prompt", "")
    if not config.GEMINI_API_KEY:
        return jsonify({"error": "Set GEMINI_API_KEY in .env to use AI images"}), 400
    workdir = config.TEMP_DIR / uuid.uuid4().hex[:8]
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        path = image_source._ai_generate(prompt, workdir)
        if not path:
            return jsonify({"error": "AI image generation failed"}), 500
        url = f"/output/_ai_{Path(path).name}"
        import shutil
        shutil.copy(path, config.OUTPUT_DIR / Path(path).name)
        return jsonify({"url": url})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/output/<path:f>")
def output_file(f):
    return send_file(config.OUTPUT_DIR / f, mimetype="video/mp4")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    if "topic" not in request.form and "topic" not in request.values:
        return jsonify({"error": "topic is required"}), 400

    orientation = request.form.get("orientation", "vertical")
    if orientation not in config.RESOLUTIONS:
        orientation = "vertical"
    w, h = config.RESOLUTIONS[orientation]
    workdir = config.TEMP_DIR / uuid.uuid4().hex[:8]
    workdir.mkdir(parents=True, exist_ok=True)

    # optional uploaded background images (story mode)
    local_images = []
    for f in request.files.getlist("images"):
        if f and f.filename:
            p = workdir / f"img_{len(local_images)}{Path(f.filename).suffix or '.png'}"
            f.save(str(p))
            local_images.append(p)

    bg_song_path = None
    if request.files.get("bg_song"):
        bf = request.files["bg_song"]
        bg_song_path = workdir / f"bgsong{Path(bf.filename).suffix or '.mp3'}"
        bf.save(str(bg_song_path))

    opts = {
        "topic": request.form.get("topic", "").strip(),
        "orientation": orientation,
        "voice": request.form.get("voice", "en-US-AriaNeural"),
        "use_ai": bool(request.form.get("use_ai")),
        "music_volume": float(request.form.get("music_volume", 35)),
        "subtitle_style": {
            "font": request.form.get("font", "Arial"),
            "size": int(request.form.get("size", 60)),
            "color": request.form.get("color", "#ffffff"),
            "outline": request.form.get("outline", "#000000"),
            "position": request.form.get("position", "bottom"),
            "bold": bool(request.form.get("bold")),
            "box": bool(request.form.get("box")),
            "highlight": bool(request.form.get("highlight")),
        },
        "local_images": local_images or None,
        "bg_song_path": bg_song_path,
    }

    def gen():
        yield from run_pipeline(opts)

    return Response(gen(), mimetype="text/event-stream")


@app.route("/api/lyric/generate", methods=["POST"])
def api_lyric_generate():
    if "song_file" not in request.files:
        return jsonify({"error": "song_file is required"}), 400

    orientation = request.form.get("orientation", "vertical")
    if orientation not in config.RESOLUTIONS:
        orientation = "vertical"
    w, h = config.RESOLUTIONS[orientation]

    job_id = uuid.uuid4().hex[:8]
    workdir = config.TEMP_DIR / job_id
    workdir.mkdir(parents=True, exist_ok=True)

    song = request.files["song_file"]
    song_path = workdir / f"song{Path(song.filename).suffix or '.mp3'}"
    song.save(str(song_path))

    uploaded_image = None
    if request.files.get("image_file"):
        img = request.files["image_file"]
        uploaded_image = workdir / f"upload{Path(img.filename).suffix or '.png'}"
        img.save(str(uploaded_image))

    lyrics_mode = request.form.get("lyrics_mode", "auto")
    if lyrics_mode == "file" and request.files.get("lyrics_file"):
        lf = request.files["lyrics_file"]
        lyrics_text = lf.read().decode("utf-8", errors="ignore")
        lyrics_filename = lf.filename
    else:
        lyrics_text = request.form.get("lyrics_text", "")
        lyrics_filename = None
    theme = request.form.get("theme", "")

    style = {
        "font": request.form.get("font", "Dancing Script"),
        "size": int(request.form.get("size", 72)),
        "text_color": request.form.get("text_color", "#ffffff"),
        "highlight_color": request.form.get("highlight_color", "#ff5ca8"),
        "outline_color": request.form.get("outline_color", "#000000"),
        "position": request.form.get("position", "center"),
        "bold": bool(request.form.get("bold")),
        "box": bool(request.form.get("box")),
        "preview": bool(request.form.get("preview")),
    }
    opts = {
        "song_path": song_path,
        "w": w, "h": h,
        "image_mode": request.form.get("image_mode", "procedural"),
        "uploaded_image": uploaded_image,
        "image_url": request.form.get("image_url"),
        "image_query": request.form.get("image_query"),
        "image_prompt": request.form.get("image_prompt"),
        "lyrics_text": lyrics_text,
        "lyrics_filename": lyrics_filename,
        "lyrics_mode": lyrics_mode,
        "theme": theme,
        "style": style,
        "auto_sync": bool(request.form.get("auto_sync")),
        "kenburns": bool(request.form.get("kenburns")),
        "orientation": orientation,
    }

    def gen():
        yield from run_lyric_pipeline(opts)

    return Response(gen(), mimetype="text/event-stream")


def run_lyric_pipeline(opts):
    workdir = config.TEMP_DIR / uuid.uuid4().hex[:8]
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        yield _ev("progress", "Reading song…")
        song_path = opts["song_path"]
        duration = lyrics_align.song_duration(song_path)

        yield _ev("progress", "Preparing background image…")
        image_path = image_source.get_image(
            opts["image_mode"], workdir, opts["w"], opts["h"],
            uploaded=opts.get("uploaded_image"),
            image_url=opts.get("image_url"),
            query=opts.get("image_query"),
            prompt=opts.get("image_prompt"),
        )

        yield _ev("progress", "Processing lyrics…")
        orig_mode = opts.get("lyrics_mode", "text")
        lyrics_text = opts.get("lyrics_text", "")
        if orig_mode == "auto":
            yield _ev("progress", "Generating lyrics from the song's theme…")
            gen_lines = lyrics_align.generate_lyrics(opts.get("theme", ""))
            lyrics_text = "\n".join(gen_lines)
            opts["auto_sync"] = True  # force vocal sync in auto mode
        lines = lyrics_align.parse_lyrics(lyrics_text, opts.get("lyrics_filename"))
        if not lines:
            yield _ev("error", "No lyrics found.")
            return
        has_times = any(ln["start"] is not None for ln in lines)
        if opts.get("auto_sync") and not has_times:
            try:
                lines = lyrics_align.auto_align(lines, song_path)
                yield _ev("progress", "Auto-synced lyrics to the song (vocals aligned).")
            except Exception as exc:
                yield _ev("progress", f"Vocal auto-sync unavailable ({exc}); timing evenly.")
        lines = lyrics_align.finalize_timings(lines, duration)

        yield _ev("progress", "Building styled subtitles…")
        ass_path = workdir / "lyrics.ass"
        lyric_renderer.build_ass(lines, opts["style"], opts["w"], opts["h"], ass_path)

        yield _ev("progress", "Rendering video…")
        out_name = f"lyric_{uuid.uuid4().hex[:8]}_{opts['orientation']}.mp4"
        out_path = config.OUTPUT_DIR / out_name
        lyric_renderer.render(image_path, song_path, ass_path,
                              opts["w"], opts["h"], out_path, duration,
                              kenburns=opts["kenburns"])

        yield _ev("done", "Lyric reel ready!", url=f"/output/{out_name}",
                  duration=round(duration, 1))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        yield _ev("error", f"Failed: {exc}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
