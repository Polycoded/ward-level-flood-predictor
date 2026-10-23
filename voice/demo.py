"""Create a LiveKit room + listener token for the voice-agent demo.

Prereqs (see docs/voice.md):
  1. uv sync --extra voice
  2. .env has LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, OPENAI_API_KEY
  3. python voice/family_agent.py dev     (leave this running)

Then run:
  python voice/demo.py --ward-name "Ward 168" --risk-level high --rainfall 120

Open the printed meet URL in a browser, allow the microphone, and the agent will
join and speak the alert.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from urllib.parse import quote

from dotenv import load_dotenv

from voice import token_server

load_dotenv()


def build_metadata(args: argparse.Namespace) -> str:
    return json.dumps({
        "ward_name": args.ward_name,
        "risk_level": args.risk_level,
        "depth_band": args.depth_band,
        "rainfall_mm": args.rainfall,
        "duration_hours": args.duration,
        "language": args.language,
        "exercise": True,
    })


def meet_url(livekit_url: str, token: str) -> str:
    return (
        "https://meet.livekit.io/?liveKitUrl="
        f"{quote(livekit_url, safe='')}&token={quote(token, safe='')}"
    )


async def run(args: argparse.Namespace) -> int:
    metadata = build_metadata(args)
    room = args.room

    created = await token_server.create_room(room, metadata)
    listener_token = token_server.create_access_token(
        identity=args.identity, room=created["name"], metadata=metadata
    )

    url = os.getenv("LIVEKIT_URL", "wss://your-project.livekit.cloud")
    print("\n=== Voice alert demo ===")
    print(f"Room:      {created['name']} ({created['sid']})")
    print(f"LiveKit:   {url}")
    print(f"Ward:      {args.ward_name} · {args.risk_level} · {args.language}")
    print(f"Token:     {listener_token[:40]}...")
    print("\nOpen this URL in the browser (allow microphone):\n")
    print(meet_url(url, listener_token))
    print("\nKeep `python voice/family_agent.py dev` running in another terminal.")
    print("Everything is labelled Exercise.\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a LiveKit room for the voice demo")
    parser.add_argument("--ward-name", default="Ward 168")
    parser.add_argument("--risk-level", default="high",
                        choices=["very_low", "low", "moderate", "high", "very_high"])
    parser.add_argument("--depth-band", default="0.5-1.0m",
                        choices=["none", "0-0.15m", "0.15-0.5m", "0.5-1.0m", "1.0m+"])
    parser.add_argument("--rainfall", type=float, default=120.0)
    parser.add_argument("--duration", type=float, default=6.0)
    parser.add_argument("--language", default="en", choices=["en", "ta"])
    parser.add_argument("--identity", default="resident")
    parser.add_argument("--room", default="flood-alert-demo")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
