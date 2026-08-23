"""Script generation: Gemini (primary) with a free offline template fallback."""
import json
import os
import re

import config


def generate_script(topic, target_duration=45, use_ai=True, lang="english"):
    """Return {"title": str, "segments": [str, ...]} for one caption per line."""
    if use_ai and config.GEMINI_API_KEY:
        try:
            return _gemini_script(topic, target_duration, lang)
        except Exception as exc:  # fall back to template so the app still works
            print(f"[script_gen] Gemini failed ({exc}); using template fallback.")
    return _template_script(topic, target_duration, lang)


def _gemini_script(topic, target_duration, lang="english"):
    import google.generativeai as genai

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL)

    if lang == "hinglish":
        lang_note = (
            "Write the script in HINGLISH: Hindi written in the Latin/English alphabet "
            "(e.g. 'Padhai kaise karein', 'Dhyaan rakho apna', 'Follow zaroor karna'). "
            "Do NOT use Devanagari."
        )
    elif lang == "hindi":
        lang_note = "Write the script in Hindi using the Devanagari script only."
    else:
        lang_note = "Write the script in English."

    prompt = (
        f"Write a short, punchy social-media video script about: {topic}.\n"
        f"{lang_note}\n"
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


def _template_script(topic, target_duration, lang="english"):
    t = topic.strip()
    low = t.lower()
    if lang == "hinglish":
        return {
            "title": (t or "Tip").title(),
            "segments": [
                f"Kya aapko pata hai {low} aapki life badal sakta hai?",
                f"Aaj hum baat karenge {low} ke sabse important points ki.",
                f"Pehla, {low} aapko sahi cheezon par focus rakhne deta hai.",
                f"Doosra, ye chhote habits banata hai jo time ke saath badhte hain.",
                f"Teesra, ye roz aapka confidence chup-chaap badhata hai.",
                f"Chhota shuruat lo, consistent raho, results khud aayenge.",
                f"Daily {low} ke aur tips ke liye follow zaroor karna.",
            ],
        }
    if lang == "hindi":
        return {
            "title": (t or "टिप").title(),
            "segments": [
                f"क्या आप जानते हैं {low} आपका जीवन बदल सकता है?",
                f"आज हम बात करेंगे {low} के सबसे ज़रूरी पॉइंट्स की।",
                f"पहला, {low} आपको सही चीज़ों पर ध्यान रखने देता है।",
                f"दूसरा, यह छोटी आदतें बनाता है जो समय के साथ बढ़ती हैं।",
                f"तीसरा, यह रोज़ आपका भरोसा चुपचाप बढ़ाता है।",
                f"छोटी शुरुआत करें, लगातार रहें, नतीजे अपने आएँगे।",
                f"रोज़ {low} की और टिप्स के लिए फ़ॉलो ज़रूर करें।",
            ],
        }
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
