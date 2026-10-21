FLOOD_ALERT_SCRIPTS = {
    "en": {
        "intro": "This is an automated flood alert from the Chennai Flood Prediction System.",
        "very_low": "No significant flood risk is expected for {ward_name} at this time.",
        "low": "Low flood risk for {ward_name}. Minor waterlogging is possible in low-lying areas.",
        "moderate": "Moderate flood risk for {ward_name}. Waterlogging up to {depth_band} is expected. Avoid low-lying areas.",
        "high": "High flood risk for {ward_name}. Significant waterlogging up to {depth_band} is expected. Move to higher ground if needed.",
        "very_high": "SEVERE FLOOD WARNING for {ward_name}. Dangerous flooding up to {depth_band} is expected. Evacuate immediately if advised by authorities.",
        "rainfall": "Rainfall forecast is {rainfall_mm} millimeters over the next 3 hours.",
        "actions": "Recommended actions: Stay indoors. Avoid underpasses and low-lying roads. Move vehicles to higher ground. Keep emergency supplies ready. Follow local authority instructions.",
        "helpline": "For emergencies, call Chennai disaster helpline 1077.",
        "outro": "Stay safe. This alert will be updated as conditions change."
    },
    "ta": {
        "intro": "இது சென்னை வெள்ளம் முன்னறிவிப்பு அமைப்பின் தானியங்கி எச்சரிக்கை.",
        "very_low": "{ward_name}க்காக ஏதாவது பெரிய வெள்ளம் அபாயம் இல்லை.",
        "low": "{ward_name}க்காக குறைந்த வெள்ளம் அபாயம். குறைந்த இடங்களில் சிறு தண்ணீர்த்தIVAL võimalம்.",
        "moderate": "{ward_name}க்காக மிதமான வெள்ளம் அபாயம். {depth_band} வரை தண்ணீர்த்தIVAL எதிர்பார்க்கப்படுகிறது. குறைந்த பகுதிகளைத் தவிர்க்கவும்.",
        "high": "{ward_name}க்காக உயர் வெள்ளம் அபாயம். {depth_band} வரை வீதமான தண்ணீர்த்தIVAL எதிர்பார்க்கப்படுகிறது. தேவையாகில் மேல் நிலைக்கு செல்லவும்.",
        "very_high": "{ward_name}க்காக கடுமையான வெள்ளம் எச்சரிக்கை. {depth_band} வரை ஆபத்தான வெள்ளம் எதிர்பார்க்கப்படுகிறது. அதிகாரிகள் அறிவுறுத்தியால் உடனே வெளியேறவும்.",
        "rainfall": "மூன்று மணி நேரத்திற்கு {rainfall_mm} மில்லிமீட்டர் மழை எதிர்பார்க்கப்படுகிறது.",
        "actions": "பரிந்துரைக்கப்படும் நடவடிக்கைகள்: வீட்டில் থাকவும். உட்சாதனங்கள் மற்றும் குறைந்த பாதைகளைத் தவிர்க்கவும். வாகனங்களை மேல் நிலைக்கு நகர்த்தவும். அவசர seurவைகளை தயார் வைத்திருங்கள். உள்ளூர் அதிகாரிகள் հրმங்களைப் பின்பற்றவும்.",
        "helpline": "அவசரநிலையில், சென்னை ദുരநிவாரண-finals 1077 Seigneur அழைக்கவும்.",
        "outro": "பாதுகாப்பாக இருங்கள். நிலைகள் மாறும்போது இந்த எச்சரிக்கை புதுப்பிக்கப்படும்."
    }
}

DEPTH_BAND_SPEAK = {
    "en": {
        "none": "no flooding",
        "0-0.15m": "ankle-deep water",
        "0.15-0.5m": "knee-deep water",
        "0.5-1.0m": "waist-deep water",
        "1.0m+": "over one meter deep water",
    },
    "ta": {
        "none": "வெள்ளம் இல்லை",
        "0-0.15m": "கால்நடை அளவு தண்ணீர்",
        "0.15-0.5m": "மூடு அளவு தண்ணீர்",
        "0.5-1.0m": "இடுப்பு அளவு தண்ணீர்",
        "1.0m+": "ஒரு மீட்டர் மேல் ஆழமான தண்ணீர்",
    }
}


def get_voice_script(ward_name: str, risk_level: str, depth_band: str, 
                     rainfall_mm: float, language: str = "en") -> str:
    lang = language if language in FLOOD_ALERT_SCRIPTS else "en"
    scripts = FLOOD_ALERT_SCRIPTS[lang]
    depth_speak = DEPTH_BAND_SPEAK[lang].get(depth_band, depth_band)
    
    parts = [
        scripts["intro"],
        scripts[risk_level].format(ward_name=ward_name, depth_band=depth_speak),
        scripts["rainfall"].format(rainfall_mm=f"{rainfall_mm:.0f}"),
        scripts["actions"],
        scripts["helpline"],
        scripts["outro"],
    ]
    
    return " ".join(parts)


def get_twiml_script(ward_name: str, risk_level: str, depth_band: str,
                     rainfall_mm: float, language: str = "en") -> str:
    script = get_voice_script(ward_name, risk_level, depth_band, rainfall_mm, language)
    
    voice_lang = "en-IN" if language == "en" else "ta-IN"
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="{voice_lang}" voice="Polly.Aditi">
        {script}
    </Say>
    <Pause length="2"/>
    <Say language="{voice_lang}" voice="Polly.Aditi">
        Press any key to repeat this message. Stay safe.
    </Say>
</Response>"""