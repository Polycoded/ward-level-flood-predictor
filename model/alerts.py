from typing import Tuple, Optional


ALERT_TEMPLATES = {
    "en": {
        "very_low": "No significant flood risk expected for {ward_name}. Rainfall: {rainfall_mm}mm.",
        "low": "Low flood risk for {ward_name}. Minor waterlogging possible. Rainfall: {rainfall_mm}mm. Stay alert.",
        "moderate": "Moderate flood risk for {ward_name}. Waterlogging expected up to {depth_band}. Rainfall: {rainfall_mm}mm. Avoid low-lying areas.",
        "high": "HIGH FLOOD RISK for {ward_name}. Significant waterlogging up to {depth_band} expected. Rainfall: {rainfall_mm}mm. Move to higher ground if needed.",
        "very_high": "SEVERE FLOOD WARNING for {ward_name}. Dangerous flooding up to {depth_band} expected. Rainfall: {rainfall_mm}mm. EVACUATE if advised by authorities.",
    },
    "ta": {
        "very_low": "{ward_name}印度洪水风险低。降雨量：{rainfall_mm}毫米。",
        "low": "{ward_name}印度洪水风险低。可能有轻微积水。降雨量：{rainfall_mm}毫米。请保持警惕。",
        "moderate": "{ward_name}印度洪水风险中等。预计积水深度达{depth_band}。降雨量：{rainfall_mm}毫米。避免前往低洼地区。",
        "high": "{ward_name}印度洪水风险高！预计严重积水达{depth_band}。降雨量：{rainfall_mm}毫米。如有需要请前往高地。",
        "very_high": "{ward_name}印度严重洪水警告！预计危险性洪水达{depth_band}。降雨量：{rainfall_mm}毫米。如当局建议请立即撤离。",
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
    channel: str = "sms"
) -> Tuple[str, Optional[str]]:
    lang = language if language in ALERT_TEMPLATES else "en"
    
    template = ALERT_TEMPLATES[lang].get(risk_level, ALERT_TEMPLATES[lang]["moderate"])
    depth_label = DEPTH_BAND_LABELS[lang].get(depth_band, depth_band)
    
    message = template.format(
        ward_name=ward_name,
        rainfall_mm=f"{rainfall_mm:.0f}",
        depth_band=depth_label
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