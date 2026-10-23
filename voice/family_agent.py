"""LiveKit voice agent (livekit-agents 1.x) that delivers a ward flood alert.

Run (after `uv sync --extra voice` and setting LiveKit + OpenAI env vars):

    python voice/family_agent.py dev

The worker uses automatic dispatch: it joins a room when a participant joins it.
Create the room and a listener token with `python voice/demo.py`.
"""

from __future__ import annotations

import json
import os

import structlog
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
)
from livekit.plugins import openai, silero

load_dotenv()

logger = structlog.get_logger()

STT_MODEL = os.getenv("VOICE_STT_MODEL", "gpt-4o-mini-transcribe")
LLM_MODEL = os.getenv("VOICE_LLM_MODEL", "gpt-4.1-mini")
TTS_MODEL = os.getenv("VOICE_TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("VOICE_TTS_VOICE", "alloy")


class FloodAlertAgent:
    def __init__(self, ward_name: str, risk_level: str, depth_band: str,
                 rainfall_mm: float, language: str = "en", duration_hours: float = 3.0):
        self.ward_name = ward_name
        self.risk_level = risk_level
        self.depth_band = depth_band
        self.rainfall_mm = rainfall_mm
        self.language = language if language in ("en", "ta") else "en"
        self.duration_hours = duration_hours

    def script(self) -> str:
        from voice.scripts import get_voice_script

        return get_voice_script(
            self.ward_name, self.risk_level, self.depth_band,
            self.rainfall_mm, self.language, self.duration_hours,
        )

    def instructions(self) -> str:
        lang_prompt = "Speak only in Tamil." if self.language == "ta" else "Speak only in English."
        return f"""You are a calm flood-alert voice assistant for Chennai wards. {lang_prompt}

Deliver this exercise alert for {self.ward_name}, then answer the resident's questions briefly:
{self.script()}

Rules:
- This is an EXERCISE broadcast; say so if asked.
- Do not invent shelter names or addresses. Advise moving to higher ground and following
  official instructions; for emergencies call 1077.
- Keep answers short, practical and reassuring. Never claim the alert is a calibrated
  flood forecast; call it an early warning based on rainfall and terrain.
- If the person says they are safe, acknowledge it and remind them to stay alert.
"""


def _job_data(ctx: JobContext) -> dict:
    raw = ctx.room.metadata or ctx.job.metadata or "{}"
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        logger.warning("Invalid LiveKit metadata; using defaults")
        return {}


async def entrypoint(ctx: JobContext) -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is required for speech-to-text, LLM and text-to-speech. "
            "Set it in .env before starting the voice worker."
        )

    data = _job_data(ctx)
    agent = FloodAlertAgent(
        ward_name=data.get("ward_name", "Ward 168"),
        risk_level=data.get("risk_level", "high"),
        depth_band=data.get("depth_band", "0.5-1.0m"),
        rainfall_mm=float(data.get("rainfall_mm", 120.0)),
        language=data.get("language", "en"),
        duration_hours=float(data.get("duration_hours", 6.0)),
    )

    await ctx.connect()

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=openai.STT(model=STT_MODEL, language=agent.language),
        llm=openai.LLM(model=LLM_MODEL),
        tts=openai.TTS(model=TTS_MODEL, voice=TTS_VOICE),
    )

    await session.start(
        agent=Agent(instructions=agent.instructions()),
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

    await session.say(agent.script(), allow_interruptions=True)
    logger.info("Voice alert delivered", ward=agent.ward_name, language=agent.language)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
