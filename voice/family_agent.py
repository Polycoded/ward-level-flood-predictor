"""LiveKit voice agent that delivers a ward flood alert.

Providers:
- LLM: DeepSeek (OpenAI-compatible) when DEEPSEEK_API_KEY is set.
- STT: local faster-whisper (DeepSeek has no audio endpoints).
- TTS: Microsoft Edge TTS (free, Tamil + English).
- Unless OPENAI_API_KEY is set and DeepSeek is absent, in which case the
  original OpenAI STT/LLM/TTS path is used.

Run (after `uv sync --extra voice`):

    python voice/family_agent.py dev

Create a room + listener token with `python voice/demo.py`.
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
    stt,
)
from livekit.plugins import openai, silero

load_dotenv()

logger = structlog.get_logger()

# OpenAI path (fallback)
STT_MODEL = os.getenv("VOICE_STT_MODEL", "gpt-4o-mini-transcribe")
LLM_MODEL = os.getenv("VOICE_LLM_MODEL", "gpt-4.1-mini")
TTS_MODEL = os.getenv("VOICE_TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("VOICE_TTS_VOICE", "alloy")

# DeepSeek + local audio path
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
WHISPER_MODEL = os.getenv("VOICE_WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("VOICE_WHISPER_DEVICE", "auto")
WHISPER_COMPUTE = os.getenv("VOICE_WHISPER_COMPUTE", "int8")
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE") or None


def provider_name() -> str:
    if os.getenv("DEEPSEEK_API_KEY", "").strip():
        return "deepseek"
    if os.getenv("OPENAI_API_KEY", "").strip():
        return "openai"
    raise RuntimeError(
        "Set DEEPSEEK_API_KEY (recommended) or OPENAI_API_KEY in .env before "
        "starting the voice worker."
    )


def build_llm():
    if provider_name() == "deepseek":
        return openai.LLM(
            model=DEEPSEEK_MODEL,
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url=DEEPSEEK_BASE_URL,
        )
    return openai.LLM(model=LLM_MODEL)


def build_stt(language: str):
    if provider_name() == "deepseek":
        from voice.plugins.faster_whisper_stt import FasterWhisperSTT

        return FasterWhisperSTT(
            model_size=WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE,
            language=language,
        )
    return openai.STT(model=STT_MODEL, language=language)


def build_tts(language: str):
    if provider_name() == "deepseek":
        from voice.plugins.edge_tts import EdgeTTS

        return EdgeTTS(language=language, voice=EDGE_TTS_VOICE)
    return openai.TTS(model=TTS_MODEL, voice=TTS_VOICE)


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

    vad = silero.VAD.load()
    stt_impl = build_stt(agent.language)
    if not getattr(stt_impl.capabilities, "streaming", False):
        stt_impl = stt.StreamAdapter(stt=stt_impl, vad=vad)

    session = AgentSession(
        vad=vad,
        stt=stt_impl,
        llm=build_llm(),
        tts=build_tts(agent.language),
    )

    await session.start(
        agent=Agent(instructions=agent.instructions()),
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

    await session.say(agent.script(), allow_interruptions=True)
    logger.info(
        "Voice alert delivered",
        ward=agent.ward_name,
        language=agent.language,
        provider=provider_name(),
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
