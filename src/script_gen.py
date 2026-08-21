"""Script generation: Gemini (primary) with a free offline template fallback."""
import json
import os
import re

import config


def generate_script(topic, target_duration=45, use_ai=True):
    """Return {"title": str, "segments": [str, ...]} for one caption per line."""
    if use_ai and config.GEMINI_API_KEY:
        try:
            return _gemini_script(topic, target_duration)
        except Exception as exc:  # fall back to template so the app still works
            print(f"[script_gen] Gemini failed ({exc}); using template fallback.")
    return _template_script(topic, target_duration)


def _gemini_script(topic, target_duration):
    import google.generativeai as genai

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL)

    prompt = (
        f"Write a short, punchy social-media video script about: {topic}.\n"
        f"Target spoken length is about {target_duration} seconds.\n"
        "Requirements:\n"
        "- Start with a strong hook.\n"
        "- Include 3 quick points.\n"
        "- End with a call to action / follow prompt.\n"
        "- Each 'segment' must be ONE short sentence (max 18 words) that works "
        "as a single subtitle/caption line.\n"
        "Respond with STRICT JSON only, no markdown fences:\n"
        '{"title": string, "segments": [string, ...]}'
    )

    resp = model.generate_content(prompt)
    text = resp.text or ""
    text = re.sub(r"```(?:json)?", "", text).strip().strip("`").strip()
    data = json.loads(text)
    data["segments"] = [str(s).strip() for s in data.get("segments", []) if str(s).strip()]
    if not data["segments"]:
        raise ValueError("Gemini returned no usable segments")
    data["title"] = str(data.get("title", topic)).strip()
    return data


def _template_script(topic, target_duration):
    t = topic.strip()
    low = t.lower()
    segments = [
        f"Did you know {low} could change how you see the world?",
        f"Today we're breaking down the most important things about {low}.",
        f"First, {low} helps you focus on what truly matters.",
        f"Second, it builds small habits that compound over time.",
        f"Third, it quietly boosts your confidence every single day.",
        f"Start small, stay consistent, and the results will follow.",
        f"Follow for more on {low}, every single day.",
    ]
    return {"title": t.title(), "segments": segments}
