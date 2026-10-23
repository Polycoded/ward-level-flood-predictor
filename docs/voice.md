# Voice agent demo (LiveKit + DeepSeek)

The voice agent speaks the ward alert in English or Tamil, then answers short
questions ("where do I go?", "is it safe to drive?"). LiveKit carries the audio;
DeepSeek runs the conversation; speech-to-text runs locally with
`faster-whisper`; text-to-speech uses Microsoft Edge TTS. **No OpenAI key is
needed.**

Everything is labelled **Exercise**. The agent never invents shelter addresses;
it advises higher ground and the 1077 helpline.

## Stack

| Part | Component | Key needed |
|---|---|---|
| Audio transport | LiveKit Cloud | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` |
| LLM | DeepSeek (`deepseek-chat`, OpenAI-compatible) | `DEEPSEEK_API_KEY` |
| Speech-to-text | `faster-whisper` (local, English + Tamil) | none |
| Text-to-speech | Microsoft Edge TTS (free, `en-IN` / `ta-IN`) | none |

If `DEEPSEEK_API_KEY` is empty but `OPENAI_API_KEY` is set, the agent falls back
to OpenAI STT/LLM/TTS.

## 1. Install the voice extra

```powershell
uv sync --extra voice
```

This installs `livekit-agents`, `faster-whisper` and `edge-tts`.

## 2. Credentials in `.env`

```dotenv
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# optional
VOICE_WHISPER_MODEL=small      # tiny/base/small/medium; small is a good CPU default
VOICE_WHISPER_DEVICE=auto      # cpu / cuda / auto
VOICE_WHISPER_COMPUTE=int8     # int8 for CPU, float16 for GPU
# EDGE_TTS_VOICE=en-IN-NeerjaNeural
```

The first transcription downloads the Whisper model (about 0.5 GB for `small`)
from Hugging Face.

## 3. Start the agent worker (terminal 1)

```powershell
.venv\Scripts\python.exe voice\family_agent.py dev
```

Leave it running. It registers with LiveKit and uses automatic dispatch: it joins
a room when a listener joins that room.

## 4. Create a room + listener token (terminal 2)

English:

```powershell
.venv\Scripts\python.exe voice\demo.py --ward-name "Ward 168" --risk-level high --rainfall 120 --duration 6 --language en
```

Tamil:

```powershell
.venv\Scripts\python.exe voice\demo.py --ward-name "Ward 168" --risk-level very_high --depth-band 1.0m+ --rainfall 200 --duration 6 --language ta
```

Open the printed `https://meet.livekit.io/?...` URL in Chrome or Edge, allow the
microphone, and the agent joins and speaks the alert. Ask a question afterwards
to show the conversational part.

## 5. Run the API alongside (optional)

The voice demo does not need the API. For the map/dashboard:

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

If the demo must ring a real phone, use the existing Twilio path:

1. Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`.
2. Build TwiML with `voice.scripts.get_twiml_script(...)` and host it, or call
   `integrations.notifications.make_voice_call(to, twiml_url)`.

This reaches any phone without the browser but has no back-and-forth conversation.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Set DEEPSEEK_API_KEY ...` | Add the key to `.env`; restart the worker. |
| Worker starts but never joins | Start `demo.py` **after** the worker; the agent joins when the listener joins the room. |
| First reply is slow | Whisper downloads the model on first use; later starts are fast. |
| No audio / mic blocked | Allow microphone for `meet.livekit.io`; use headphones to avoid echo. |
| `401` from LiveKit | Key/secret do not match the project URL. |
| Tamil speech sounds wrong | Set `EDGE_TTS_VOICE=ta-IN-PallaviNeural` or `ta-IN-ValluvarNeural`. |
| Whisper misses Tamil | Try `VOICE_WHISPER_MODEL=medium` (slower), or use the OpenAI fallback. |
| Agent speaks but does not hear you | Check the browser input device; Silero VAD needs real mic input. |

## Limits

- DeepSeek supplies only the LLM; audio is local Whisper + Edge TTS. Edge TTS is
  an online service and needs internet.
- Browsers cannot run the agent in the background; the demo page must stay open.
- Costs: DeepSeek chat is billed per token; Whisper and Edge TTS are free/local.
