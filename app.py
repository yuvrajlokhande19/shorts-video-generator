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
import src.video_splitter as video_splitter
import src.movie_metadata as movie_metadata

app = Flask(__name__, static_folder=None)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB max upload

# In-memory store of finished lyric reels so they can be re-edited/re-rendered.
LYRIC_JOBS = {}


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
        script = script_gen.generate_script(topic, target_duration=45,
                                            use_ai=use_ai,
                                            lang=opts.get("script_lang", "english"))
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


# ============ MOVIE SPLITTER API ============

@app.route("/api/movie/metadata", methods=["POST"])
def api_movie_metadata():
    """Fetch movie metadata from various sources."""
    data = request.get_json(force=True, silent=True) or {}
    query = data.get("query", "").strip()
    language = data.get("language", "en-US")
    
    if not query:
        return jsonify({"error": "query is required"}), 400
    
    try:
        info = movie_metadata.get_movie_metadata(query, language)
        if info:
            return jsonify({
                "title": info.title,
                "original_title": info.original_title,
                "year": info.year,
                "overview": info.overview,
                "poster_url": info.poster_url,
                "backdrop_url": info.backdrop_url,
                "genres": info.genres,
                "runtime": info.runtime,
                "language": info.language,
                "imdb_id": info.imdb_id,
                "tmdb_id": info.tmdb_id,
                "source": info.source
            })
        else:
            # Fallback: extract from filename
            title = movie_metadata.MovieMetadataFetcher().extract_title_from_filename(query)
            return jsonify({
                "title": title,
                "source": "filename"
            })
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@app.route("/api/movie/split", methods=["POST"])
def api_movie_split():
    """Split a movie/video into 30-second reel segments."""
    if "video_file" not in request.files:
        return jsonify({"error": "video_file is required"}), 400

    video = request.files["video_file"]
    if not video or not video.filename:
        return jsonify({"error": "No video file selected"}), 400

    # Get form parameters
    movie_name = request.form.get("movie_name", "").strip()
    if not movie_name:
        movie_name = Path(video.filename).stem

    segment_duration = float(request.form.get("segment_duration", config.SPLITTER_DEFAULTS["segment_duration"]))
    font_size = int(request.form.get("font_size", config.SPLITTER_DEFAULTS["font_size"]))
    font_color = request.form.get("font_color", config.SPLITTER_DEFAULTS["font_color"])
    outline_color = request.form.get("outline_color", config.SPLITTER_DEFAULTS["outline_color"])
    font_family = request.form.get("font_family", config.SPLITTER_DEFAULTS["font_family"])
    movie_name_position = request.form.get(
        "movie_name_position", config.SPLITTER_DEFAULTS["movie_name_position"]
    )
    part_text_position = request.form.get(
        "part_text_position", config.SPLITTER_DEFAULTS["part_text_position"]
    )
    pad_last_segment = request.form.get("pad_last_segment", "true").lower() in (
        "true",
        "1",
        "on"
    )
    background_color = request.form.get(
        "background_color", config.SPLITTER_DEFAULTS["background_color"]
    )

    # Save uploaded video
    job_id = uuid.uuid4().hex[:8]
    workdir = config.TEMP_DIR / job_id
    workdir.mkdir(parents=True, exist_ok=True)

    video_path = workdir / f"source{Path(video.filename).suffix or '.mp4'}"
    video.save(str(video_path))

    try:
        splitter = video_splitter.VideoSplitter(workdir)
        info = splitter.get_video_info(video_path)
        duration = info["duration"]

        segments = splitter.calculate_segments(duration)
        total_parts = len(segments)

        output_paths = splitter.split_video(
            input_path=video_path,
            movie_name=movie_name,
            output_dir=config.OUTPUT_DIR,
            segment_duration=segment_duration,
            font_size=font_size,
            font_color=font_color,
            outline_color=outline_color,
            font_family=font_family,
            movie_name_position=movie_name_position,
            part_text_position=part_text_position,
            pad_last_segment=pad_last_segment,
            background_color=background_color,
        )

        reel_urls = [f"/output/{p.name}" for p in output_paths]

        return jsonify(
            {
                "success": True,
                "movie_name": movie_name,
                "total_parts": total_parts,
                "reel_urls": reel_urls,
                "message": f"Created {len(output_paths)} reel(s)!",
            }
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed: {str(e)}"}), 500


@app.route("/api/movie/preview", methods=["POST"])
def api_movie_preview():
    """Generate a preview of how the text overlay will look."""
    data = request.get_json(force=True, silent=True) or {}
    
    movie_name = data.get("movie_name", "Movie Title")
    part_number = data.get("part_number", 1)
    total_parts = data.get("total_parts", 10)
    font_size = data.get("font_size", config.SPLITTER_DEFAULTS["font_size"])
    font_color = data.get("font_color", config.SPLITTER_DEFAULTS["font_color"])
    outline_color = data.get("outline_color", config.SPLITTER_DEFAULTS["outline_color"])
    font_family = data.get("font_family", config.SPLITTER_DEFAULTS["font_family"])
    movie_name_position = data.get("movie_name_position", config.SPLITTER_DEFAULTS["movie_name_position"])
    part_text_position = data.get("part_text_position", config.SPLITTER_DEFAULTS["part_text_position"])
    
    # Return preview config for frontend rendering
    return jsonify({
        "movie_name": movie_name,
        "part_text": f"Part {part_number} of {total_parts}",
        "font_size": font_size,
        "font_color": font_color,
        "outline_color": outline_color,
        "font_family": font_family,
        "movie_name_position": movie_name_position,
        "part_text_position": part_text_position,
    })


# ============ EXISTING API ENDPOINTS ============

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
        "script_lang": request.form.get("script_lang", "english"),
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
    is_draft = request.form.get("lyrics_mode") == "draft" or bool(request.form.get("draft"))
    lyrics_lang = request.form.get("lyrics_lang", "hinglish")
    theme = request.form.get("theme", "")

    # Draft mode: just write the lyrics (no song required).
    if is_draft:
        def draft():
            lines = lyrics_align.generate_lyrics(theme, n=12, lang=lyrics_lang)
            yield _ev("done", "Lyrics drafted", type2="lyrics",
                      lyrics="\n".join(lines))
        return Response(draft(), mimetype="text/event-stream")

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
        "lyrics_lang": lyrics_lang,
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
    job_id = uuid.uuid4().hex[:8]
    try:
        yield _ev("progress", "Reading song…")
        song_path = opts["song_path"]
        duration = lyrics_align.song_duration(song_path)

        yield _ev("progress", "Preparing background image…")
        if opts["image_mode"] == "auto":
            image_path = image_source.get_images_auto(
                opts.get("theme", ""), opts.get("lyrics_text", ""),
                workdir, opts["w"], opts["h"])
        else:
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
        transcribed = None
        if orig_mode == "auto":
            yield _ev("progress", "Listening to the song and writing its real lyrics…")
            try:
                wl = {"hinglish": "hi", "hindi": "hi", "english": "en"}.get(
                    opts.get("lyrics_lang", "hinglish"), None)
                transcribed = lyrics_align.transcribe_lyrics(song_path, lang=wl)
                if opts.get("lyrics_lang") == "hinglish":
                    transcribed = lyrics_align.romanize_lines(transcribed)
                yield _ev("progress", "Synced the song's own lyrics (vocals transcribed).")
            except Exception as exc:
                print(f"[lyrics] transcription failed: {exc}")
                yield _ev("progress", f"Could not read the song's lyrics ({exc}); writing from theme instead.")

        if transcribed:
            lines = transcribed
        else:
            if orig_mode == "auto":
                gen_lines = lyrics_align.generate_lyrics(
                    opts.get("theme", ""), n=12, lang=opts.get("lyrics_lang", "hinglish"))
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
        final_lyrics = "\n".join(ln["text"] for ln in lines)

        yield _ev("progress", "Building styled subtitles…")
        ass_path = workdir / "lyrics.ass"
        lyric_renderer.build_ass(lines, opts["style"], opts["w"], opts["h"], ass_path)

        yield _ev("progress", "Rendering video…")
        out_name = f"lyric_{job_id}_{opts['orientation']}.mp4"
        out_path = config.OUTPUT_DIR / out_name
        lyric_renderer.render(image_path, song_path, ass_path,
                              opts["w"], opts["h"], out_path, duration,
                              kenburns=opts["kenburns"])

        # remember the job so it can be re-edited/re-rendered
        LYRIC_JOBS[job_id] = {
            "song_path": str(song_path),
            "image_path": [str(p) for p in lyric_renderer._as_list(image_path)],
            "style": opts["style"],
            "lyrics": final_lyrics,
            "lyrics_lang": opts.get("lyrics_lang", "hinglish"),
            "w": opts["w"], "h": opts["h"],
            "orientation": opts["orientation"],
            "kenburns": opts["kenburns"],
        }

        yield _ev("done", "Lyric reel ready!", url=f"/output/{out_name}",
                  duration=round(duration, 1), job_id=job_id, lyrics=final_lyrics)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        yield _ev("error", f"Failed: {exc}")


@app.route("/api/lyric/regenerate", methods=["POST"])
def api_lyric_regenerate():
    """Re-render a previously created reel with edited lyrics / style."""
    job_id = request.form.get("job_id")
    job = LYRIC_JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job id"}), 400

    lyrics_text = request.form.get("lyrics_text", job["lyrics"]).strip()
    style = dict(job["style"])
    for fld, key in (("font", "font"), ("size", "size"), ("text_color", "text_color"),
                     ("highlight_color", "highlight_color"),
                     ("outline_color", "outline_color"), ("position", "position"),
                     ("bold", "bold"), ("box", "box"), ("preview", "preview")):
        if request.form.get(fld) not in (None, ""):
            val = request.form.get(fld)
            if fld in ("size",):
                val = int(val)
            elif fld in ("bold", "box", "preview"):
                val = val in ("on", "true", "1")
            style[key] = val
    kenburns = request.form.get("kenburns", "on") in ("on", "true", "1")

    def gen():
        workdir = config.TEMP_DIR / uuid.uuid4().hex[:8]
        workdir.mkdir(parents=True, exist_ok=True)
        new_id = uuid.uuid4().hex[:8]
        try:
            yield _ev("progress", "Reading song…")
            song_path = job["song_path"]
            duration = lyrics_align.song_duration(song_path)
            lines = lyrics_align.parse_lyrics(lyrics_text)
            if not lines:
                yield _ev("error", "No lyrics found.")
                return
            lines = lyrics_align.finalize_timings(lines, duration)

            yield _ev("progress", "Building styled subtitles…")
            ass_path = workdir / "lyrics.ass"
            lyric_renderer.build_ass(lines, style, job["w"], job["h"], ass_path)

            yield _ev("progress", "Rendering video…")
            out_name = f"lyric_{new_id}_{job['orientation']}.mp4"
            out_path = config.OUTPUT_DIR / out_name
            lyric_renderer.render(job["image_path"], song_path, ass_path,
                                  job["w"], job["h"], out_path, duration,
                                  kenburns=kenburns)

            # update the stored job with the new edits
            LYRIC_JOBS[new_id] = dict(job, lyrics=lyrics_text, style=style,
                                      kenburns=kenburns)
            yield _ev("done", "Reel updated!", url=f"/output/{out_name}",
                      duration=round(duration, 1), job_id=new_id, lyrics=lyrics_text)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            yield _ev("error", f"Failed: {exc}")

    return Response(gen(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
