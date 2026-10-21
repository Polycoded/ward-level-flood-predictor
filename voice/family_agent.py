import os
import structlog
from typing import Optional
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.voice_assistant import VoiceAssistant
from livekit.plugins import openai, silero

logger = structlog.get_logger()

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "wss://your-project.livekit.cloud")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class FloodAlertAgent:
    def __init__(self, ward_name: str, risk_level: str, depth_band: str, 
                 rainfall_mm: float, language: str = "en"):
        self.ward_name = ward_name
        self.risk_level = risk_level
        self.depth_band = depth_band
        self.rainfall_mm = rainfall_mm
        self.language = language
    
    def get_instructions(self) -> str:
        lang_prompt = "Speak in Tamil." if self.language == "ta" else "Speak in English."
        
        risk_descriptions = {
            "en": {
                "very_low": "no significant flood risk",
                "low": "low flood risk with minor waterlogging possible",
                "moderate": f"moderate flood risk with waterlogging up to {self.depth_band}",
                "high": f"high flood risk with significant waterlogging up to {self.depth_band}",
                "very_high": f"severe flood warning with dangerous flooding up to {self.depth_band}",
            },
            "ta": {
                "very_low": "பெரிய வெள்ளம் அபாயம் இல்லை",
                "low": "குறைந்த வெள்ளம் அபாயம், சிறு தண்ணீர்த்தIVAL возможно",
                "moderate": f"மிதமான வெள்ளம் அபாயம், {self.depth_band} வரை தண்ணீர்த்தIVAL",
                "high": f"உயர் வெள்ளம் அபாயம், {self.depth_band} வரை வீதமான தண்ணீர்த்தIVAL",
                "very_high": f"கடுமையான வெள்ளம் எச்சரிக்கை, {self.depth_band} வரை ஆபத்தான வெள்ளம்",
            }
        }
        
        risk_desc = risk_descriptions[self.language].get(self.risk_level, risk_descriptions[self.language]["moderate"])
        
        return f"""You are a flood alert voice assistant for Chennai wards. {lang_prompt}

Current alert for {self.ward_name}:
- Risk level: {self.risk_level}
- Description: {risk_desc}
- Rainfall forecast: {self.rainfall_mm:.0f} millimeters over 3 hours

Your task: Deliver this alert clearly and calmly to the household. 
Provide actionable guidance:
1. Stay indoors if possible
2. Avoid low-lying areas and underpasses
3. Move vehicles to higher ground
4. Keep emergency kit ready
5. Follow local authority instructions
6. For emergencies, call 1077 (Chennai disaster helpline)

Speak naturally, with empathy but without panic. Keep responses concise.
"""
    
    async def start(self, ctx: JobContext):
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        
        vad = silero.VAD.load()
        
        assistant = VoiceAssistant(
            vad=vad,
            stt=openai.STT.with_groq(model="whisper-large-v3") if OPENAI_API_KEY else None,
            llm=openai.LLM.with_groq(model="llama-3.1-70b-versatile") if OPENAI_API_KEY else None,
            tts=openai.TTS.with_groq(model="playai-tts") if OPENAI_API_KEY else None,
            chat_ctx=llm.ChatContext().append(
                role="system",
                text=self.get_instructions()
            ),
        )
        
        await assistant.start(ctx.room)
        
        await assistant.say(
            f"Hello, this is an automated flood alert for {self.ward_name}. "
            f"Current risk level is {self.risk_level.replace('_', ' ')}. "
            f"Expected rainfall is {self.rainfall_mm:.0f} millimeters. "
            f"Please stay safe and follow local authority guidance."
        )


async def entrypoint(ctx: JobContext):
    metadata = ctx.job.metadata
    import json
    data = json.loads(metadata) if metadata else {}
    
    agent = FloodAlertAgent(
        ward_name=data.get("ward_name", "Unknown Ward"),
        risk_level=data.get("risk_level", "moderate"),
        depth_band=data.get("depth_band", "0.15-0.5m"),
        rainfall_mm=data.get("rainfall_mm", 100.0),
        language=data.get("language", "en")
    )
    
    await agent.start(ctx)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))