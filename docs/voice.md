# Voice agent demo (LiveKit + OpenAI)

The voice agent speaks the ward alert in English or Tamil, then answers short
questions ("where do I go?", "is it safe to drive?"). It uses LiveKit Cloud for
audio and OpenAI for speech-to-text, the LLM and text-to-speech.

Everything is labelled **Exercise**. The agent never invents shelter addresses;
it advises higher ground and the 1077 helpline.

## What you need

| Item | Where |
|---|---|
| LiveKit Cloud project (free tier is enough) | https://cloud.livekit.io |
| `LIVEKIT_URL` (`wss://...livekit.cloud`), `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | LiveKit project → Settings → Keys |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |

The browser demo page (`https://meet.livekit.io`) needs no install.

## 1. Install the voice extra

```powershell
uv sync --extra voice
```

This installs `livekit-agents 1.x` plus the OpenAI and Silero plugins.

## 2. Put credentials in `.env`

```dotenv
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-...

# optional overrides
VOICE_STT_MODEL=gpt-4o-mini-transcribe
VOICE_LLM_MODEL=gpt-4.1-mini
VOICE_TTS_MODEL=gpt-4o-mini-tts
VOICE_TTS_VOICE=alloy
```

## 3. Start the agent worker (terminal 1)

```powershell
.venv\Scripts\python.exe voice\family_agent.py dev
```

Leave it running. It registers with LiveKit and uses **automatic dispatch**: it
joins a room when a listener joins that room.

## 4. Create a room + listener token (terminal 2)

English:

```powershell
.venv\Scripts\python.exe voice\demo.py --ward-name "Ward 168" --risk-level high --rainfall 120 --duration 6 --language en
```

Tamil:

```powershell
.venv\Scripts\python.exe voice\demo.py --ward-name "Ward 168" --risk-level very_high --depth-band 1.0m+ --rainfall 200 --duration 6 --language ta
```

The command prints a `https://meet.livekit.io/?liveKitUrl=...&token=...` URL.
Open it in Chrome or Edge, allow the microphone, and the agent will join and
speak the alert. Ask a question afterwards to show the conversational part.

## 5. Run the API alongside (optional)

The voice demo does not need the API. If you also want the map/dashboard:

```powershell
.venv\Scripts\python.exe -m uvicorn api.main:app --reload
```

## How the alert data reaches the agent

`voice/demo.py` writes the alert into **room metadata**:

```json
{"ward_name": "Ward 168", "risk_level": "high", "depth_band": "0.5-1.0m",
 "rainfall_mm": 120, "duration_hours": 6, "language": "en", "exercise": true}
```

`voice/family_agent.py` reads `ctx.room.metadata` (falling back to job metadata)
and builds the spoken script with `voice/scripts.py`. To use a real computed
alert, take the ward's `risk_level`, `depth_band` and rainfall from
`POST /api/v1/risk` and pass them to `demo.py`.

## Phone call instead of a browser (Twilio)

If the demo needs to ring a real phone rather than a browser, use the existing
Twilio path:

1. Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`.
2. Build TwiML with `voice.scripts.get_twiml_script(...)` and host it, or call
   `integrations.notifications.make_voice_call(to, twiml_url)`.

This reaches any phone without the browser but has no back-and-forth conversation.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `OPENAI_API_KEY is required` | Add it to `.env`; restart the worker. |
| Worker starts but never joins | Start `demo.py` **after** the worker; the agent joins when the listener joins the room. |
| No audio / mic blocked | Allow microphone for `meet.livekit.io`; use headphones to avoid echo. |
| `401` from LiveKit | Key/secret do not match the project URL. |
| Tamil sounds wrong | Try `VOICE_TTS_VOICE=alloy` or `nova`; OpenAI TTS handles Tamil but accents vary. |
| Agent speaks but does not hear you | Check the browser input device; Silero VAD needs actual mic input. |
| First start is slow | Silero VAD downloads its model once. |

## Limits

- This is a cloud demo (OpenAI + LiveKit), not an offline/GGUF model. The repo
  declares `livekit-agents` as an optional `voice` extra so the API image stays
  small.
- Browsers cannot run the agent in the background; the demo page must stay open.
- Costs: OpenAI STT/LLM/TTS are billed per use; keep demo sessions short.
