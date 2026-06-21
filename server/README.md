# Quietcare — Backend

Cloud backend for Quietcare, an always-on elderly-safety companion. A phone
client streams short events over a WebSocket when something looks wrong. The
backend runs **two cooperating Claude agents**:

- **elder-agent** — reasons about the event, runs a voice check-in, fuses the
  signals (trigger source + transcript + whether the elder responded), and
  decides to resolve or escalate.
- **caretaker-agent** — triages an escalation off the message bus and alerts the
  human caretaker via Twilio.

Everything runs **end-to-end with zero credentials** — each provider falls back
to a mock when its API key is absent.

## Stack

Python 3.11 · FastAPI (WS `/ws` + `GET /health`) · Anthropic Messages API
(tool-use) · Deepgram (STT/TTS) · Redis (memory) · Twilio (telephony) · BAND
(message bus) · Sentry (optional).

## Quickstart (all-mock, no keys)

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt          # core (all-mock mode)
# pip install -r requirements-optional.txt  # only to enable real providers
cp .env.example .env            # optional; all keys may stay blank

# terminal 1 — run the server
uvicorn app.main:app --host 0.0.0.0 --port 8080

# terminal 2 — drive the full loop
python mock/send_trigger.py --scenario emergency   # -> escalation + Twilio
python mock/send_trigger.py --scenario fine        # -> resolves silently
```

`GET http://localhost:8080/health` reports which provider impls are active
(`mock` vs real).

## Definition of done

- `--scenario emergency`: trigger → elder-agent check-in (`speak`+`listen`) →
  no clear response → `notify_caretaker_agent` over the bus → caretaker-agent
  triages → Twilio SMS (real if key present, else logged as `WOULD SEND`).
- `--scenario fine`: resolves silently with **no** caretaker notification.
- Both print a clear, labeled trace; the server logs the FSM transitions.

## Architecture

```
server/
  app/
    main.py            # FastAPI app: /health + WS /ws, background trigger tasks
    config.py          # env settings + capability flags
    protocol.py        # protocol v1 message models (mirrors shared/protocol.md)
    session.py         # per-elder session, trigger orchestration, caretaker svc
    state_machine.py   # explicit escalation FSM + safety invariants
    sentry_init.py     # optional Sentry init + capture()
    providers/
      llm.py           # LLM iface: AnthropicLLM + deterministic MockLLM
      voice.py         # Voice iface: DeepgramVoice + MockVoice
      memory.py        # Memory iface: RedisMemory + MockMemory (seeds Margaret)
      telephony.py     # Telephony iface: TwilioTelephony + MockTelephony
      bus.py           # MessageBus iface: BandBus + InProcessBus (default)
      factory.py       # auto-selects real vs mock per available config
    agents/
      base.py          # provider-agnostic tool-use loop
      elder.py         # elder-agent tools + system prompt
      caretaker.py     # caretaker-agent tools + system prompt
  mock/
    send_trigger.py    # CLI client simulator (--scenario fine|emergency)
  requirements.txt
  .env.example
```

## Escalation state machine

```
idle -> triggered -> checking_in -> (resolved | escalating)
                  \-> escalating              (only if hard_fall)
escalating -> caretaker_notified -> (human_ack | 911_gated)
```

The **LLM decides** transitions (via which tools it calls); the **code enforces**
them and the invariants:

- **911 is never reachable without explicit human confirmation** —
  `escalate_911` is gated in `state_machine.gate_911(human_confirmed=...)` and
  refuses otherwise. The agent is also instructed never to call it autonomously.
- **Every escalation passes through a check-in first**, unless the trigger is an
  unambiguous hard fall (`hard_fall`).

## Providers & fallbacks

| Provider   | Real impl        | Enabled when…                | Mock fallback                         |
|------------|------------------|------------------------------|---------------------------------------|
| LLM        | Anthropic        | `ANTHROPIC_API_KEY` set      | scripted, data-driven agent policy    |
| Voice      | Deepgram         | `DEEPGRAM_API_KEY` set       | canned transcript / silent WAV        |
| Memory     | Redis            | `REDIS_URL` set              | in-memory dict (seeded with Margaret) |
| Telephony  | Twilio           | all `TWILIO_*` set           | logs `WOULD SEND/CALL …`              |
| Bus        | BAND             | `BAND_API_KEY` + `BAND_BASE_URL` | in-process async fan-out          |
| Sentry     | Sentry           | `SENTRY_DSN` set             | no-op (still logs)                    |

## Configuration

See `.env.example`. **Never hardcode keys.** Every key is optional; the system
runs fully mocked without any.

## Out of scope

The mobile app, real fall-detection ML, booking automation (`book_task` is a
stub), any UI, anything in `/client`. The client is simulated via
`mock/send_trigger.py`.
