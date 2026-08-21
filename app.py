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
        clip_paths = stock.get_clips(topic, timings, w, h, workdir)

        yield _ev("progress", "Building subtitles…")
        ass_path = workdir / "subs.ass"
        subtitles.build_ass(timings, style, ass_path)

        yield _ev("progress", "Adding background music…")
        music_path = music.get_music(total_dur, workdir)

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


@app.route("/output/<path:f>")
def output_file(f):
    return send_file(config.OUTPUT_DIR / f, mimetype="video/mp4")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    opts = request.get_json(force=True, silent=True) or {}
    if not opts.get("topic"):
        return jsonify({"error": "topic is required"}), 400

    q = []

    def gen():
        yield from run_pipeline(opts)

    return Response(gen(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
