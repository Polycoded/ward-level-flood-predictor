ALERT_TEMPLATES = {
    "en": {
        level: "Uncalibrated index: " + level.replace("_", " ") +
        ". {ward_name}. Rainfall: {rainfall_mm}mm. Not a flood forecast. Follow official advice."
        for level in ("very_low", "low", "moderate", "high", "very_high")
    },
    "ta": {
        level: "அளவுத்திருத்தம் செய்யப்படாத குறியீடு: " + label +
        ". {ward_name}. மழை: {rainfall_mm}mm. வெள்ள முன்னறிவிப்பு அல்ல."
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
    channel: str = "sms"
) -> tuple[str, str | None]:
    lang = language if language in ALERT_TEMPLATES else "en"

    template = ALERT_TEMPLATES[lang].get(risk_level, ALERT_TEMPLATES[lang]["moderate"])

    message = template.format(
        ward_name=ward_name,
        rainfall_mm=f"{rainfall_mm:.0f}"
    )

    # Multipart is acceptable; never silently remove safety/disclaimer content.

    whatsapp_deeplink = None
    if channel == "whatsapp":
        whatsapp_number = WHATSAPP_NUMBERS.get(lang, WHATSAPP_NUMBERS["en"])
        import urllib.parse
        encoded_msg = urllib.parse.quote(message)
        whatsapp_deeplink = f"https://wa.me/{whatsapp_number}?text={encoded_msg}"

    return message, whatsapp_deeplink


def format_alert_for_channel(message: str, channel: str, max_length: int = None) -> str:
    # max_length is a compatibility argument, not permission to truncate content.
    return message


def sms_info(message: str) -> dict:
    """Pack whole characters; never split a GSM escape or UTF-16 surrogate pair."""
    basic = '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà'
    extended = '^{}\\[~]|€\f'
    gsm = all(c in basic or c in extended for c in message)
    widths = [2 if c in extended else 1 for c in message] if gsm else [
        len(c.encode("utf-16-le")) // 2 for c in message]
    units = sum(widths)
    single, multi = (160, 153) if gsm else (70, 67)
    segments, used = 1, 0
    if units > single:
        for width in widths:
            if used + width > multi:
                segments += 1
                used = 0
            used += width
    return {"encoding": "GSM-7" if gsm else "UCS-2", "units": units,
            "segments": segments, "singleLimit": single}


def exercise_message(candidate: dict, *, exercise_id: str, language: str = "en",
                     shelter: dict | None = None) -> dict:
    """Content only: does not approve, send, or invent shelter information."""
    from urllib.parse import urlparse

    from model.alert_contract import digest, integer, scenario_input, text
    if candidate.get("mode") != "Exercise" or candidate.get("status") != "pending":
        raise ValueError("Only pending Exercise candidates may be rendered")
    text(exercise_id, "exercise_id")
    integer(candidate.get("ward_id"), "ward_id", 1)
    official = text(candidate.get("ward_number"), "ward_number")
    forcing = scenario_input(candidate["rainfall"])
    text(candidate.get("candidate_id"), "candidate_id")
    if language not in ("en", "ta"):
        raise ValueError("Supported Exercise languages: en, ta (draft)")
    amount, hours = f'{forcing["rainfall_mm"]:g}', f'{forcing["duration_hours"]:g}'
    action = "Exercise only: review this ward's information with the exercise coordinator."
    if language == "en":
        message = (f"EXERCISE {exercise_id}. Ward {official}. {amount} mm total over {hours} h. "
                   "This index is uncalibrated, not a flood forecast. " + action)
    else:
        action = "பயிற்சி மட்டும்: இந்த வார்டின் தகவலை பயிற்சி ஒருங்கிணைப்பாளருடன் மதிப்பாய்வு செய்யவும்."
        message = (f"EXERCISE {exercise_id} — பயிற்சி. வார்டு {official}. "
                   f"{hours} மணி நேர மொத்த மழை {amount} mm. "
                   "இது அளவுத்திருத்தம் செய்யப்படாத குறியீடு; வெள்ள முன்னறிவிப்பு அல்ல. " + action)
    if shelter is not None:
        name, ref, url = (text(shelter.get(key), f"shelter.{key}") for key in ("name", "source_ref", "url"))
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Shelter requires a traceable HTTPS information URL")
        message += f" Supplied shelter information (availability/routes unverified): {name}; {url}; source: {ref}."
    return {"mode": "Exercise", "exercise_id": exercise_id, "candidate_id": candidate["candidate_id"],
            "candidate_digest": digest(candidate), "ward_id": candidate["ward_id"], "ward_number": official,
            "language": language, "headline": f"EXERCISE {exercise_id}: Ward {official}",
            "text": message, "instruction": action, "sms": sms_info(message),
            "language_review": "pending_native_speaker" if language == "ta" else "draft_exercise_content"}
