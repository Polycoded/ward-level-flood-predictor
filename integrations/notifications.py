import os
import structlog
from typing import List, Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

logger = structlog.get_logger()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

_client: Optional[Client] = None


def get_twilio_client() -> Optional[Client]:
    global _client
    if _client is None and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        _client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return _client


async def send_sms(to: str, body: str) -> Dict[str, Any]:
    client = get_twilio_client()
    if not client:
        logger.warning("Twilio not configured, simulating SMS send")
        return {"success": True, "sid": "mock_sid", "simulated": True}
    
    if not TWILIO_PHONE_NUMBER:
        logger.error("TWILIO_PHONE_NUMBER not configured")
        return {"success": False, "error": "Sender number not configured"}
    
    try:
        message = client.messages.create(
            body=body,
            from_=TWILIO_PHONE_NUMBER,
            to=to
        )
        logger.info("SMS sent", to=to, sid=message.sid)
        return {"success": True, "sid": message.sid, "simulated": False}
    except TwilioException as e:
        logger.error("Twilio SMS error", to=to, error=str(e))
        return {"success": False, "error": str(e)}


async def send_whatsapp(to: str, body: str) -> Dict[str, Any]:
    client = get_twilio_client()
    if not client:
        logger.warning("Twilio not configured, simulating WhatsApp send")
        return {"success": True, "sid": "mock_wa_sid", "simulated": True}
    
    try:
        message = client.messages.create(
            body=body,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=f"whatsapp:{to}"
        )
        logger.info("WhatsApp sent", to=to, sid=message.sid)
        return {"success": True, "sid": message.sid, "simulated": False}
    except TwilioException as e:
        logger.error("Twilio WhatsApp error", to=to, error=str(e))
        return {"success": False, "error": str(e)}


async def make_voice_call(to: str, twiml_url: str) -> Dict[str, Any]:
    client = get_twilio_client()
    if not client:
        logger.warning("Twilio not configured, simulating voice call")
        return {"success": True, "sid": "mock_call_sid", "simulated": True}
    
    if not TWILIO_PHONE_NUMBER:
        logger.error("TWILIO_PHONE_NUMBER not configured")
        return {"success": False, "error": "Sender number not configured"}
    
    try:
        call = client.calls.create(
            twiml=twiml_url,
            from_=TWILIO_PHONE_NUMBER,
            to=to
        )
        logger.info("Voice call initiated", to=to, sid=call.sid)
        return {"success": True, "sid": call.sid, "simulated": False}
    except TwilioException as e:
        logger.error("Twilio voice call error", to=to, error=str(e))
        return {"success": False, "error": str(e)}


async def send_alert_to_ward(
    ward_name: str,
    phone_numbers: List[str],
    message: str,
    whatsapp_deeplink: Optional[str] = None,
    language: str = "en"
) -> List[Dict[str, Any]]:
    results = []
    
    for phone in phone_numbers:
        sms_result = await send_sms(phone, message)
        results.append({"channel": "sms", "phone": phone, **sms_result})
        
        if whatsapp_deeplink:
            wa_message = f"{message}\n\nWhatsApp: {whatsapp_deeplink}"
            wa_result = await send_whatsapp(phone, wa_message)
            results.append({"channel": "whatsapp", "phone": phone, **wa_result})
    
    return results


def generate_twiml_for_alert(ward_name: str, risk_level: str, depth_band: str, 
                              rainfall_mm: float, language: str = "en") -> str:
    messages = {
        "en": {
            "very_low": f"No significant flood risk expected for {ward_name}.",
            "low": f"Low flood risk for {ward_name}. Minor waterlogging possible.",
            "moderate": f"Moderate flood risk for {ward_name}. Waterlogging expected up to {depth_band}.",
            "high": f"High flood risk for {ward_name}. Significant waterlogging up to {depth_band} expected.",
            "very_high": f"Severe flood warning for {ward_name}. Dangerous flooding up to {depth_band} expected. Evacuate if advised.",
        },
        "ta": {
            "very_low": f"{ward_name}க்காக பெரிய வெள்ளம் அபாயம் இல்லை.",
            "low": f"{ward_name}க்காக குறைந்த வெள்ளம் அபாயம். சிறு தண்ணீர்த்தーヴல் mahdollம்.",
            "moderate": f"{ward_name}க்காக மிதமான வெள்ளம் அபாயம். {depth_band} வரை தண்ணீர்த்த palacio.",
            "high": f"{ward_name}க்காக உயர் வெள்ளம் அபாயம். {depth_band} வரை வீதமான தண்ணீர்த்த palace.",
            "very_high": f"{ward_name}க்காக கடுமையான வெள்ளம் எச்சரிக்கை. {depth_band} வரை ஆபத்தான வெள்ளம் எதிர்பார்க்கப்படுகிறது. அதிகாரிகள் அறிவுறுத்தியால் ತಡவாமல் வெளியேறவும்.",
        }
    }
    
    lang = language if language in messages else "en"
    message_text = messages[lang].get(risk_level, messages[lang]["moderate"])
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="{'en-IN' if language == 'en' else 'ta-IN'}" voice="Polly.Aditi">
        {message_text} Rainfall forecast is {rainfall_mm:.0f} millimeters. 
        Stay safe and follow local authority instructions.
    </Say>
</Response>"""