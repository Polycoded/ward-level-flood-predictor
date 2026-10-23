"""Local speech-to-text plugin backed by faster-whisper.

DeepSeek has no audio endpoints, so the voice agent runs Whisper locally.
The model is loaded lazily on first use (first run downloads it).
"""

from __future__ import annotations

import asyncio
import io

from livekit.agents import stt
from livekit.agents.types import NOT_GIVEN, NotGivenOr
from livekit.agents.utils import is_given


class FasterWhisperSTT(stt.STT):
    def __init__(self, *, model_size: str = "small", device: str = "auto",
                 compute_type: str = "int8", language: str = "en") -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=False, interim_results=False)
        )
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._language = language if language in ("en", "ta") else "en"
        self._engine = None

    @property
    def model(self) -> str:
        return f"faster-whisper-{self._model_size}"

    @property
    def provider(self) -> str:
        return "faster-whisper"

    def _ensure_engine(self):
        if self._engine is None:
            from faster_whisper import WhisperModel

            self._engine = WhisperModel(
                self._model_size, device=self._device, compute_type=self._compute_type
            )
        return self._engine

    async def _recognize_impl(
        self,
        buffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options,
    ) -> stt.SpeechEvent:
        from livekit import rtc

        wav_bytes = rtc.combine_audio_frames(buffer).to_wav_bytes()
        lang = language if is_given(language) else self._language

        def _transcribe() -> tuple[str, str]:
            engine = self._ensure_engine()
            segments, info = engine.transcribe(
                io.BytesIO(wav_bytes), language=lang, vad_filter=False, beam_size=1
            )
            text = "".join(segment.text for segment in segments).strip()
            return text, getattr(info, "language", None) or lang

        text, detected = await asyncio.to_thread(_transcribe)
        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(language=detected, text=text)],
        )
