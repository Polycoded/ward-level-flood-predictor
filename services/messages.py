"""Short, actionable alert copy in English and Tamil.

These are deliberately plain-language and fit one SMS where possible. They are
clearly labelled as an exercise until an official turns exercise mode off.
"""

from __future__ import annotations


def _rain(rainfall_mm: float) -> str:
    return f"{rainfall_mm:.0f}"


def alert_text(alert_type: str, ward_name: str, rainfall_mm: float,
               duration_hours: float, language: str = "en") -> str:
    ta = language == "ta"
    if alert_type == "warning":
        if ta:
            return (
                f"வெள்ள எச்சரிக்கை — {ward_name}. கனமழை ({_rain(rainfall_mm)}மிமீ / "
                f"{duration_hours:.0f}மணி). சுரங்கப்பாதை மற்றும் தாழ்வான சாலைகளைத் தவிர்க்கவும். "
                "அருகிலுள்ள தங்குமிடத்திற்குச் செல்லவும். பயிற்சி மட்டும்."
            )
        return (
            f"FLOOD WARNING - {ward_name}. Heavy rain ({_rain(rainfall_mm)}mm / "
            f"{duration_hours:.0f}h). Avoid underpasses and low roads. Go to the nearest "
            "shelter if water rises. Exercise only."
        )
    if ta:
        return (
            f"வெள்ள கண்காணிப்பு — {ward_name}. மழை எதிர்பார்க்கப்படுகிறது "
            f"({_rain(rainfall_mm)}மிமீ / {duration_hours:.0f}மணி). தாழ்வான சாலைகளைத் தவிர்க்கவும். "
            "பயிற்சி மட்டும்."
        )
    return (
        f"Flood watch - {ward_name}. Rain expected ({_rain(rainfall_mm)}mm / "
        f"{duration_hours:.0f}h). Avoid low-lying roads and stay alert. Exercise only."
    )


def join_confirmation(ward_id: int, language: str = "en") -> str:
    if language == "ta":
        return f"வார்டு {ward_id} வெள்ள எச்சரிக்கை சந்தா சேர்க்கப்பட்டது. நிறுத்த STOP என அனுப்பவும்."
    return f"Subscribed to flood alerts for Ward {ward_id}. Reply STOP to unsubscribe."


def stop_confirmation(language: str = "en") -> str:
    if language == "ta":
        return "சந்தா நீக்கப்பட்டது. மீண்டும் சேர JOIN <வார்டு எண்> என அனுப்பவும்."
    return "You are unsubscribed. Reply JOIN <ward number> to subscribe again."


def help_text(language: str = "en") -> str:
    if language == "ta":
        return (
            "JOIN <வார்டு எண்> - வெள்ள எச்சரிக்கை பெற; "
            "STOP - சந்தா நீக்க; HELP - இந்த உதவி. பயிற்சி மட்டும்."
        )
    return (
        "JOIN <ward number> - get flood alerts for your ward; "
        "STOP - unsubscribe; HELP - this message. Exercise only."
    )


def unknown_command(language: str = "en") -> str:
    if language == "ta":
        return "புரியவில்லை. JOIN <வார்டு எண்>, STOP அல்லது HELP என அனுப்பவும்."
    return "Sorry, I did not understand. Reply JOIN <ward number>, STOP or HELP."
