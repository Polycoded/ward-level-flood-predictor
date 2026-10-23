from typing import Tuple, Optional


ALERT_TEMPLATES = {
    "en": {
        level: "Uncalibrated index: " + level.replace("_", " ") +
        ". Rain: {rainfall_mm}mm/{duration_hours}h. {ward_name}. Not a flood forecast. Follow official advice."
        for level in ("very_low", "low", "moderate", "high", "very_high")
    },
    "ta": {
        level: "அளவுத்திருத்தம் செய்யப்படாத குறியீடு: " + label +
        ". மழை: {rainfall_mm}mm/{duration_hours}h. {ward_name}. வெள்ள முன்னறிவிப்பு அல்ல."
        for level, label in (("very_low", "மிகக் குறைவு"), ("low", "குறைவு"),
                             ("moderate", "மிதமானது"), ("high", "அதிகம்"),
                             ("very_high", "மிக அதிகம்"))
    }
}

DEPTH_BAND_LABELS = {
    "en": {
        "none": "no flooding",
        "0-0.15m": "ankle-deep",
        "0.15-0.5m": "knee-deep",
        "0.5-1.0m": "waist-deep",
        "1.0m+": "over 1 meter",
    },
    "ta": {
        "none": "வெள்ளம் இல்லை",
        "0-0.15m": "கால்நடை அளவு",
        "0.15-0.5m": "மூடு அளவு",
        "0.5-1.0m": "இடுப்பு அளவு",
        "1.0m+": "1 மீட்டர் மேல்",
    }
}

WHATSAPP_NUMBERS = {
    "en": "919876543210",
    "ta": "919876543210",
}


def generate_alert_messages(
    ward_name: str,
    risk_level: str,
    depth_band: str,
    rainfall_mm: float,
    language: str = "en",
    channel: str = "sms",
    *, duration_hours: float = 3.0
) -> Tuple[str, Optional[str]]:
    lang = language if language in ALERT_TEMPLATES else "en"
    
    template = ALERT_TEMPLATES[lang].get(risk_level, ALERT_TEMPLATES[lang]["moderate"])
    
    message = template.format(
        ward_name=ward_name,
        rainfall_mm=f"{rainfall_mm:g}",
        duration_hours=f"{duration_hours:g}"
    )
    
    if channel == "sms" and len(message) > 160:
        message = message[:157] + "..."
    
    whatsapp_deeplink = None
    if channel == "whatsapp":
        whatsapp_number = WHATSAPP_NUMBERS.get(lang, WHATSAPP_NUMBERS["en"])
        import urllib.parse
        encoded_msg = urllib.parse.quote(message)
        whatsapp_deeplink = f"https://wa.me/{whatsapp_number}?text={encoded_msg}"
    
    return message, whatsapp_deeplink


def format_alert_for_channel(message: str, channel: str, max_length: int = None) -> str:
    if channel == "sms":
        max_len = max_length or 160
    elif channel == "whatsapp":
        max_len = max_length or 4096
    elif channel == "voice":
        max_len = max_length or 500
    else:
        max_len = max_length or 160
    
    if len(message) > max_len:
        return message[:max_len - 3] + "..."
    return message
