"""Microsoft Edge TTS plugin for LiveKit (free, no API key, English + Tamil).

Audio is synthesized once, cached to disk, and replayed as a complete MP3. This
avoids the choppy "slow audio generation" behaviour of streaming Edge TTS chunk
by chunk, and makes repeat demo runs start instantly.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import uuid
from pathlib import Path

import edge_tts
from livekit.agents import APIConnectOptions, tts
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS

SAMPLE_RATE = 24000
DEFAULT_VOICES = {
    "en": "en-IN-NeerjaNeural",
    "ta": "ta-IN-PallaviNeural",
}
CHUNK_BYTES = 64 * 1024


def _cache_dir() -> Path:
    path = Path(os.getenv("VOICE_TTS_CACHE") or (Path(tempfile.gettempdir()) / "flood-voice-tts"))
    path.mkdir(parents=True, exist_ok=True)
    return path


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

    def _cache_path(self, text: str) -> Path:
        digest = hashlib.sha256(
            f"{self.voice}|{self.rate}|{self.volume}|{self.pitch}|{text}".encode()
        ).hexdigest()[:32]
        return _cache_dir() / f"{digest}.mp3"

    async def _synthesize_bytes(self, text: str) -> bytes:
        communicate = edge_tts.Communicate(
            text, self.voice, rate=self.rate, volume=self.volume, pitch=self.pitch
        )
        buffer = bytearray()
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                buffer.extend(chunk["data"])
        return bytes(buffer)

    async def precache(self, text: str) -> None:
        """Synthesize now so the first `say()` is instant and smooth."""
        path = self._cache_path(text)
        if path.exists() and path.stat().st_size > 0:
            return
        audio = await self._synthesize_bytes(text)
        if not audio:
            return
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(audio)
        temporary.replace(path)

    def synthesize(self, text: str, *,
                   conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS) -> tts.ChunkedStream:
        return EdgeChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class EdgeChunkedStream(tts.ChunkedStream):
    def __init__(self, *, tts: EdgeTTS, input_text: str,
                 conn_options: APIConnectOptions) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts_impl: EdgeTTS = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        path = self._tts_impl._cache_path(self.input_text)
        if path.exists() and path.stat().st_size > 0:
            audio = path.read_bytes()
        else:
            audio = await self._tts_impl._synthesize_bytes(self.input_text)
            if audio:
                temporary = path.with_suffix(".tmp")
                temporary.write_bytes(audio)
                temporary.replace(path)

        output_emitter.initialize(
            request_id=str(uuid.uuid4()),
            sample_rate=SAMPLE_RATE,
            num_channels=1,
            mime_type="audio/mpeg",
        )
        # Push a full buffer quickly; the emitter decodes and paces playback.
        for start in range(0, len(audio), CHUNK_BYTES):
            output_emitter.push(audio[start:start + CHUNK_BYTES])
        output_emitter.flush()
