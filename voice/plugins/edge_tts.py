"""Microsoft Edge TTS plugin for LiveKit (free, no API key, supports Tamil).

Produces 24 kHz mono MP3 through `edge-tts`, which the LiveKit AudioEmitter
decodes. Used because DeepSeek offers chat only (no speech endpoints).
"""

from __future__ import annotations

import uuid

from livekit.agents import APIConnectOptions, tts
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS

SAMPLE_RATE = 24000
DEFAULT_VOICES = {
    "en": "en-IN-NeerjaNeural",
    "ta": "ta-IN-PallaviNeural",
}


class EdgeTTS(tts.TTS):
    def __init__(self, *, language: str = "en", voice: str | None = None,
                 rate: str = "+0%", volume: str = "+0%", pitch: str = "+0Hz") -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=SAMPLE_RATE,
            num_channels=1,
        )
        self.language = language
        self.voice = voice or DEFAULT_VOICES.get(language, DEFAULT_VOICES["en"])
        self.rate = rate
        self.volume = volume
        self.pitch = pitch

    @property
    def model(self) -> str:
        return "edge-tts"

    @property
    def provider(self) -> str:
        return "microsoft-edge"

    def synthesize(self, text: str, *,
                   conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS) -> tts.ChunkedStream:
        return EdgeChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class EdgeChunkedStream(tts.ChunkedStream):
    def __init__(self, *, tts: EdgeTTS, input_text: str,
                 conn_options: APIConnectOptions) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts_impl: EdgeTTS = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        import edge_tts

        output_emitter.initialize(
            request_id=str(uuid.uuid4()),
            sample_rate=SAMPLE_RATE,
            num_channels=1,
            mime_type="audio/mpeg",
        )
        communicate = edge_tts.Communicate(
            self.input_text,
            self._tts_impl.voice,
            rate=self._tts_impl.rate,
            volume=self._tts_impl.volume,
            pitch=self._tts_impl.pitch,
        )
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                output_emitter.push(chunk["data"])
        output_emitter.flush()
