"""Pre-synthesize the demo opening so the first `say()` is instant."""

from __future__ import annotations

import asyncio

from voice.plugins.edge_tts import EdgeTTS
from voice.test_case import opening_script


async def main() -> None:
    engine = EdgeTTS(language="en")
    text = opening_script("en")
    await engine.precache(text)
    print("Voice opening cached.")


if __name__ == "__main__":
    asyncio.run(main())
