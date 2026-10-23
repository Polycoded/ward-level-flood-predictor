"""Spoken alert scripts in English and Tamil (plain language, one action per line)."""

FLOOD_ALERT_SCRIPTS = {
    "en": {
        "intro": "This is an automated flood alert from the Chennai Flood Prediction System. Exercise only.",
        "very_low": "No significant flood risk is expected for {ward_name} at this time.",
        "low": "Low flood risk for {ward_name}. Minor waterlogging is possible in low-lying areas.",
        "moderate": "Moderate flood risk for {ward_name}. Waterlogging up to {depth_band} is expected. Avoid low-lying areas.",
        "high": "High flood risk for {ward_name}. Significant waterlogging up to {depth_band} is expected. Move to higher ground if needed.",
        "very_high": "Severe flood warning for {ward_name}. Dangerous flooding up to {depth_band} is expected. Evacuate if authorities advise.",
        "rainfall": "Rainfall forecast is {rainfall_mm} millimetres over the next {duration_hours} hours.",
        "actions": "Recommended actions: stay indoors. Avoid underpasses and low-lying roads. Move vehicles to higher ground. Keep emergency supplies ready. Follow local authority instructions.",
        "helpline": "For emergencies, call the Chennai disaster helpline 1077.",
        "outro": "Stay safe. This alert will be updated as conditions change.",
    },
    "ta": {
        "intro": "இது சென்னை வெள்ள முன்னறிவிப்பு அமைப்பின் தானியங்கி வெள்ள எச்சரிக்கை. இது பயிற்சி மட்டுமே.",
        "very_low": "{ward_name} பகுதியில் தற்போது குறிப்பிடத்தக்க வெள்ள அபாயம் இல்லை.",
        "low": "{ward_name} பகுதியில் குறைந்த வெள்ள அபாயம். தாழ்வான பகுதிகளில் சிறிய தண்ணீர் தேங்கலாம்.",
        "moderate": "{ward_name} பகுதியில் மிதமான வெள்ள அபாயம். {depth_band} வரை தண்ணீர் தேங்கும். தாழ்வான பகுதிகளைத் தவிர்க்கவும்.",
        "high": "{ward_name} பகுதியில் அதிக வெள்ள அபாயம். {depth_band} வரை தண்ணீர் தேங்கும். தேவைப்பட்டால் உயரமான இடத்திற்குச் செல்லவும்.",
        "very_high": "{ward_name} பகுதியில் கடுமையான வெள்ள எச்சரிக்கை. {depth_band} வரை ஆபத்தான வெள்ளம். அதிகாரிகள் அறிவுறுத்தினால் உடனே வெளியேறவும்.",
        "rainfall": "அடுத்த {duration_hours} மணி நேரத்தில் {rainfall_mm} மில்லிமீட்டர் மழை எதிர்பார்க்கப்படுகிறது.",
        "actions": "பரிந்துரைக்கப்படும் நடவடிக்கைகள்: வீட்டிலேயே இருங்கள். சுரங்கப்பாதை மற்றும் தாழ்வான சாலைகளைத் தவிர்க்கவும். வாகனங்களை உயரமான இடத்திற்கு நகர்த்தவும். அவசரப் பொருட்களைத் தயாராக வைத்திருங்கள். உள்ளூர் அதிகாரிகளின் அறிவுறுத்தல்களைப் பின்பற்றவும்.",
        "helpline": "அவசரநிலையில், சென்னை பேரிடர் உதவி எண் 1077 ஐ அழைக்கவும்.",
        "outro": "பாதுகாப்பாக இருங்கள். நிலைமை மாறும்போது இந்த எச்சரிக்கை புதுப்பிக்கப்படும்.",
    },
}

DEPTH_BAND_SPEAK = {
    "en": {
        "none": "no flooding",
        "0-0.15m": "ankle-deep water",
        "0.15-0.5m": "knee-deep water",
        "0.5-1.0m": "waist-deep water",
        "1.0m+": "over one metre deep water",
    },
    "ta": {
        "none": "வெள்ளம் இல்லை",
        "0-0.15m": "கணுக்கால் அளவு தண்ணீர்",
        "0.15-0.5m": "முழங்கால் அளவு தண்ணீர்",
        "0.5-1.0m": "இடுப்பு அளவு தண்ணீர்",
        "1.0m+": "ஒரு மீட்டருக்கு மேல் ஆழமான தண்ணீர்",
    },
}


def get_voice_script(ward_name: str, risk_level: str, depth_band: str,
                     rainfall_mm: float, language: str = "en",
                     duration_hours: float = 3.0) -> str:
    lang = language if language in FLOOD_ALERT_SCRIPTS else "en"
    scripts = FLOOD_ALERT_SCRIPTS[lang]
    depth_speak = DEPTH_BAND_SPEAK[lang].get(depth_band, depth_band)
    level = risk_level if risk_level in scripts else "moderate"

    parts = [
        scripts["intro"],
        scripts[level].format(ward_name=ward_name, depth_band=depth_speak),
        scripts["rainfall"].format(rainfall_mm=f"{rainfall_mm:.0f}",
                                   duration_hours=f"{duration_hours:.0f}"),
        scripts["actions"],
        scripts["helpline"],
        scripts["outro"],
    ]
    return " ".join(parts)


def get_twiml_script(ward_name: str, risk_level: str, depth_band: str,
                     rainfall_mm: float, language: str = "en",
                     duration_hours: float = 3.0) -> str:
    from xml.sax.saxutils import escape

    script = get_voice_script(ward_name, risk_level, depth_band, rainfall_mm,
                              language, duration_hours)
    voice_lang = "en-IN" if language == "en" else "ta-IN"
    repeat = ("Press any key to repeat this message. Stay safe." if language != "ta"
              else "இந்தச் செய்தியை மீண்டும் கேட்க எந்த விசையையும் அழுத்தவும். பாதுகாப்பாக இருங்கள்.")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="{voice_lang}" voice="Polly.Aditi">{escape(script)}</Say>
    <Pause length="2"/>
    <Say language="{voice_lang}" voice="Polly.Aditi">{escape(repeat)}</Say>
</Response>"""
