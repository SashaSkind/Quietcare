# Quietcare — Devin Prompt: BACKEND (You)

**This is your prompt. Paste everything below the line into your Devin, pointed at the shared `quietcare` monorepo.**

The monorepo layout (created once by the team):
```
quietcare/
  client/              ← teammate's Devin works here (do not touch)
  server/              ← YOU work only here
  shared/protocol.md   ← the WebSocket contract (read-only reference for both)
  README.md
```
The §0 contract (bottom of this doc) should already be in `shared/protocol.md`.

---

**PROJECT:** You are building the cloud backend for "Quietcare," an always-on elderly-safety companion. A phone client streams short events over a WebSocket when something looks wrong. Your backend runs **two cooperating Claude agents** — an **elder-agent** (reasons about the event, runs a voice check-in, decides if it's a real emergency) and a **caretaker-agent** (triages and alerts the human via Twilio). The two agents communicate over a message bus (BAND). You build the **backend only**. The mobile client is built by a teammate in `/client`; simulate it with a script.

**REPO DISCIPLINE (important — parallel work):**
- Work **only inside the `/server` folder**. Do not modify anything outside `/server` (not `/client`, not root configs, not `/shared`).
- Commit to a branch named **`server-dev`**, not `main`. Commit frequently with clear messages.
- Treat `shared/protocol.md` as **read-only**. If you think the contract needs to change, STOP and flag it in your summary instead of editing it — changing it would break the teammate's half.

**STACK:** Python 3.11 + FastAPI (WebSocket endpoint + `/health`). Anthropic Messages API for the agents via the official SDK, with a configurable `ANTHROPIC_BASE_URL` so it can point at either the PaleBlueDot router or `api.anthropic.com`. Use a venv. Keep everything behind interfaces so missing API keys never block local testing.

**BUILD THIS, IN ORDER (everything lives under `/server`):**
1. Scaffold FastAPI with `GET /health` and a `WS /ws` endpoint implementing the server side of the protocol in `shared/protocol.md` (handle `register`, `trigger`, `audio_response`, `heartbeat`; send `speak`, `listen`, `status`, `ack`). Maintain per-connection session state keyed by `elder_id`.
2. **Provider interfaces** (each with a real impl reading env keys, and a **mock/in-memory fallback** used automatically when the key is absent):
   - `LLM` → Anthropic Messages API tool-use loop (model + base_url from env; default model `claude-sonnet-4-6`).
   - `Voice` → Deepgram STT (`transcribe(audio_b64) -> text`) + TTS (`synthesize(text) -> audio_b64`). Mock returns canned text/silence.
   - `Memory` → Redis (`get/set/list` per `elder:{id}:*`). Mock = in-memory dict. Seed a sample elder profile (Margaret, 78, on blood-pressure meds, one prior fall).
   - `Telephony` → Twilio (`send_sms(text)`, `call_voice(summary)`). Mock logs "WOULD SEND/CALL …".
   - `MessageBus` → BAND (`publish(msg)`, `subscribe(handler)`). Mock = in-process async queue (default).
3. **Elder-agent** (Claude tool-use loop). Tools: `speak_to_elder(text)` (renders TTS, sends `speak` over WS), `listen_to_elder(duration_ms)` (sends `listen`, awaits `audio_response`, returns transcript), `get_elder_profile()`, `get_recent_events()`, `log_event(event)`, `notify_caretaker_agent(severity, summary, evidence)` (publishes to the bus). On a `trigger`: pull context, transcribe the clip, run a voice check-in, **fuse signals** (acoustic source + transcript + whether the elder responded) into a decision, and either resolve silently or escalate.
4. **Caretaker-agent** (Claude tool-use loop, subscribes to the bus). Tools: `get_elder_profile()`, `send_caretaker_sms(text)`, `call_caretaker_voice(summary)`, `book_task(task)` (stub for now), `escalate_911(...)` (**gated** — must require an explicit human-confirmation flag; never callable autonomously). Triages the message and, on a real emergency, notifies the human via Twilio.
5. **Escalation state machine** (explicit, in code, not prompt-driven): `idle → triggered → checking_in → (resolved | escalating) → caretaker_notified → (human_ack | 911_gated)`. The LLM **decides** transitions; the code **enforces** them and the invariants: 911 is never reachable without human confirmation; every escalation passes through a check-in first (unless an unambiguous hard fall with no motion).
6. **Mock client** in `/server/mock/send_trigger.py`: connects to `/ws`, sends `register` + a `trigger` (bundle a short sample WAV as base64), and auto-answers any `listen` with a **configurable canned response** — support `--scenario fine` (replies "I'm fine, just dropped a pot") and `--scenario emergency` (replies with silence / "I can't get up"). Print the full exchange and clearly show whether Twilio was invoked.
7. **Sentry** init (DSN from env, optional). Wrap agent runs and tool calls so failures are captured. (A FastAPI Sentry project will be created in the dashboard; just read `SENTRY_DSN` from env.)
8. **README** in `/server` + `.env.example` listing every key as a placeholder (`ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `DEEPGRAM_API_KEY`, `TWILIO_*`, `REDIS_URL`, `BAND_*`, `SENTRY_DSN`). **Never hardcode keys.**

**DEFINITION OF DONE:** Running `python mock/send_trigger.py --scenario emergency` drives the full loop: trigger → elder-agent check-in (`speak`+`listen`) → no clear response → `notify_caretaker_agent` over the bus → caretaker-agent triages → Twilio SMS (real if key present, else logged). Running `--scenario fine` resolves silently with **no** caretaker notification. Both runs print a clear, labeled trace of the state machine. Works end-to-end with all-mock providers (no real keys required) and with real keys when present.

**OUT OF SCOPE (do NOT build):** the mobile app, real fall-detection ML, the booking automation (stub `book_task`), any UI, anything in `/client`. Simulate the client only via the mock script.

---

## §0 — SHARED CONTRACT (this is the content of `shared/protocol.md`)

**WebSocket protocol v1.** Client opens a WebSocket to the backend at `/ws`. Every message is a JSON text frame with a `type` field. All audio is base64-encoded WAV or Opus.

**CLIENT → BACKEND**
```json
{ "type": "register", "elder_id": "margaret-01" }

{
  "type": "trigger",
  "elder_id": "margaret-01",
  "ts": "2026-06-20T18:30:00Z",
  "trigger_source": "fall" | "audio_event" | "scheduled" | "manual",
  "audio_clip_b64": "<base64 audio ~3-5s, or null>",
  "frame_b64": "<base64 jpeg, or null>",
  "device_state": { "battery": 0.82, "connectivity": "wifi" }
}

{
  "type": "audio_response",
  "elder_id": "margaret-01",
  "ts": "...",
  "prompt_id": "<echo the prompt_id from the listen message>",
  "audio_clip_b64": "<base64 audio>"
}

{ "type": "heartbeat", "elder_id": "margaret-01", "ts": "...", "device_state": { } }
```

**BACKEND → CLIENT**
```json
{ "type": "speak", "prompt_id": "p1", "audio_b64": "<base64 audio>", "text": "Margaret, are you okay?" }

{ "type": "listen", "prompt_id": "p1", "duration_ms": 6000 }

{ "type": "status", "state": "idle" | "checking_in" | "escalating" | "resolved" }

{ "type": "ack", "received": "trigger" }
```

**Rules both sides obey:**
- A check-in is always: backend sends `speak`, then `listen`; client plays the audio, records `duration_ms`, replies with `audio_response` carrying the same `prompt_id`.
- **All STT/TTS happens on the backend** (Deepgram). The client only plays and records audio — it never transcribes or synthesizes.
- **The client holds NO API keys.** Anthropic, Deepgram, Twilio, BAND, Redis live on the backend only.
- The WebSocket URL is configurable on the client via `EXPO_PUBLIC_WS_URL`.
