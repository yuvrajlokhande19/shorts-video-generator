"""Background image sourcing for Lyric Reels: upload / stock / AI / procedural."""
import subprocess
import urllib.parse
import urllib.request

import config


def _crop(image_path, out_path, w, h):
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(image_path), "-vf",
         f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1",
         "-frames:v", "1", str(out_path)],
        check=True, capture_output=True,
    )


def _procedural(out_path, w, h, seed=0):
    c0, c1 = config.GRADIENTS[seed % len(config.GRADIENTS)]
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"gradients=s={w}x{h}:c0={c0}:c1={c1}:x0=0:y0=0:x1={w}:y1={h}",
         "-frames:v", "1", "-y", str(out_path)],
        check=True, capture_output=True,
    )


def _download(url, out_path):
    req = urllib.request.Request(url, headers={"User-Agent": "auto-shorts/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r, open(out_path, "wb") as f:
        f.write(r.read())


def get_image(mode, workdir, w, h, uploaded=None, image_url=None,
              query=None, prompt=None, seed=0):
    """Return path to a w x h cover-cropped image."""
    out = workdir / "bg.png"
    if mode == "upload" and uploaded:
        _crop(uploaded, out, w, h)
        return out
    if mode == "stock":
        url = image_url
        if not url and query:
            url = _stock_search(query)
        if url:
            try:
                tmp = workdir / "stock.jpg"
                _download(url, tmp)
                _crop(tmp, out, w, h)
                return out
            except Exception as exc:
                print(f"[image] stock download failed: {exc}")
        _procedural(out, w, h, seed)
        return out
    if mode == "ai":
        try:
            p = prompt or "faceless boy and girl watching each other, minimal flat illustration, soft pastel colors"
            gen = _ai_generate(p, workdir)
            if gen:
                _crop(gen, out, w, h)
                return out
        except Exception as exc:
            print(f"[image] AI generation failed: {exc}")
        _procedural(out, w, h, seed)
        return out
    # procedural default
    _procedural(out, w, h, seed)
    return out


def _stock_search(query, count=6):
    if config.PEXELS_API_KEY:
        try:
            url = ("https://api.pexels.com/v1/search?query="
                   + urllib.parse.quote(query) + f"&per_page={count}&orientation=portrait")
            req = urllib.request.Request(url, headers={"Authorization": config.PEXELS_API_KEY})
            with urllib.request.urlopen(req, timeout=30) as r:
                import json
                data = json.loads(r.read())
            photos = data.get("photos", [])
            if photos:
                return photos[0]["src"]["large"]
        except Exception as exc:
            print(f"[image] Pexels failed: {exc}")
    if config.PIXABAY_API_KEY:
        try:
            import json
            url = ("https://pixabay.com/api/?key=" + config.PIXABAY_API_KEY
                   + "&q=" + urllib.parse.quote(query)
                   + "&image_type=illustration&per_page=6&orientation=vertical")
            with urllib.request.urlopen(url, timeout=30) as r:
                data = json.loads(r.read())
            hits = data.get("hits", [])
            if hits:
                return hits[0]["largeImageURL"]
        except Exception as exc:
            print(f"[image] Pixabay failed: {exc}")
    return None


def search_images(query, count=6):
    """Return a list of {url} for stock image search (needs a key)."""
    results = []
    if config.PEXELS_API_KEY:
        try:
            import json
            url = ("https://api.pexels.com/v1/search?query="
                   + urllib.parse.quote(query) + f"&per_page={count}&orientation=portrait")
            req = urllib.request.Request(url, headers={"Authorization": config.PEXELS_API_KEY})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
            for p in data.get("photos", [])[:count]:
                results.append({"url": p["src"]["large"], "thumb": p["src"]["medium"]})
        except Exception as exc:
            print(f"[image] Pexels search failed: {exc}")
    if not results and config.PIXABAY_API_KEY:
        try:
            import json
            url = ("https://pixabay.com/api/?key=" + config.PIXABAY_API_KEY
                   + "&q=" + urllib.parse.quote(query)
                   + "&image_type=illustration&per_page=" + str(count) + "&orientation=vertical")
            with urllib.request.urlopen(url, timeout=30) as r:
                data = json.loads(r.read())
            for h in data.get("hits", [])[:count]:
                results.append({"url": h["largeImageURL"], "thumb": h["previewURL"]})
        except Exception as exc:
            print(f"[image] Pixabay search failed: {exc}")
    return results


def _ai_generate(prompt, workdir):
    import google.generativeai as genai
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-preview-image-generation")
    resp = model.generate_content(
        prompt,
        generation_config={"response_modalities": ["IMAGE"]},
    )
    for part in resp.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            import base64
            out = workdir / "ai.png"
            with open(out, "wb") as f:
                f.write(base64.b64decode(part.inline_data.data))
            return out
    return None
