# Quietcare

**An ambient AI safety companion for elderly care.** _Cal Hacks 2026 · June 20–21_

> "Your phone doesn't blow up every time grandpa drops a spoon — only when something is actually wrong."

Elderly people living alone face a dangerous gap: when something goes wrong — a
fall, a stroke, choking, sudden confusion — help often arrives far too late.
Quietcare watches ambiently, runs a calm spoken check-in when something looks
off, and loops in the right person **fast, without false alarms**.

---

## How it works

A phone app watches motion + audio cheaply on-device. When something looks
wrong it streams a short event to the cloud over a WebSocket. The backend then
runs **two cooperating Claude agents**:

- **elder-agent** — reasons about the event, runs a spoken voice check-in, fuses
  the signals (trigger source + transcript + whether the elder responded + any
  non-speech acoustic distress), and decides to **resolve** or **escalate**.
- **caretaker-agent** — triages an escalation off the message bus and alerts the
  human caretaker via SMS / voice call, and can request **human-authorized 911**.

```
 phone (client)              cloud (server)                          humans
 ┌──────────────┐  WS /ws   ┌───────────────┐   BAND bus  ┌────────────────┐
 │ fall detect  │ ───────►  │  elder-agent  │ ──@mention─►│ caretaker-agent│
 │ audio buffer │  trigger  │  (Claude)     │             │   (Claude)     │
 │ check-in I/O │ ◄───────  │  voice + ML   │             │  Twilio SMS/call│
 └──────────────┘  speak/   └───────────────┘             └───────┬────────┘
                   listen                                          │ gated
                                                                   ▼
                                                        human-authorized 911
```

Everything runs **end-to-end with zero credentials** — every external provider
sits behind an interface with an automatic **mock fallback**.

---

## Repository layout

| Path | What's there |
| --- | --- |
| [`server/`](server/README.md) | FastAPI backend, the two Claude agents, all providers, escalation FSM. |
| [`client/`](client/README.md) | Expo (React Native) device app: on-device fall detection, rolling audio buffer, check-in I/O, camera snapshot. |
| [`server/app/band_mesh/`](server/app/band_mesh) | Standalone BAND agent daemons (elder + caretaker) for the full `@mention` mesh. |
| [`shared/protocol.md`](shared/protocol.md) | The WebSocket protocol v1 contract shared by client + server. |
| [`PROJECT.md`](PROJECT.md) | Full project brief, pitch notes, and sponsor rationale. |
| `design-videos/` | UI mocks + walkthrough recordings. |

---

## Quickstart

### Backend (all-mock, no keys)

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # all keys may stay blank

# terminal 1 — run the server
uvicorn app.main:app --host 0.0.0.0 --port 8080

# terminal 2 — drive the full loop
python mock/send_trigger.py --scenario emergency   # -> escalation + caretaker alert
python mock/send_trigger.py --scenario fine        # -> resolves silently
```

`GET http://localhost:8080/health` reports which provider impls are active
(`mock` vs real).

### Client (device app)

See [`client/README.md`](client/README.md) for the Expo dev-build + Android
install steps. The client holds **no API keys** and talks to the backend purely
over the WebSocket contract.

---

## Safety model

The **LLM decides** transitions (via which tools it calls); the **code enforces**
them and the hard invariants:

- **911 is never reachable without explicit human confirmation.** `escalate_911`
  is gated in `state_machine.gate_911(human_confirmed=…)`, re-sanctioned by a
  policy gate, and dispatch only fires on a token-verified human approval.
- **Every escalation passes through a check-in first**, unless the trigger is an
  unambiguous hard fall.
- **Agents never autonomously dial emergency services** — they can only *request*
  human authorization.

```
idle -> triggered -> checking_in -> (resolved | escalating)
                  \-> escalating              (only if hard_fall)
escalating -> caretaker_notified -> (human_ack | 911_gated)
```

---

## Sponsor / integration stack

Every integration is wired behind an interface with an automatic mock fallback.

| Provider | Layer | Role |
| --- | --- | --- |
| **PaleBlueDot** (TokenRouter) | Inference | Anthropic-compatible gateway serving **Claude**; direct Anthropic is the fallback. |
| **BAND** | Inter-agent bus | Carries escalations between the elder- and caretaker-agents; powers the full `@mention` mesh. |
| **Deepgram** | Voice I/O | Real STT (`nova-2`) + TTS (`aura-asteria-en`) for the spoken check-in. |
| **YAMNet** (TFLite) | Audio-scene ML | Non-speech distress tagging (thud / scream / glass) fused into the decision. |
| **Redis** | Memory | Elder profile, meds, history, recent events. |
| **Twilio** | Emergency channel | Real SMS / voice calls to the caretaker + gated 911 dispatch + inbound "how's mom?" recap. |
| **Browserbase** | Everyday-care | Off-critical-path automation (e.g. medication refill) via a cloud browser. |
| **Arize AX** | Evals / tracing | OpenTelemetry tracing of the agent tool-use loop and every Claude call. |
| **ArmorIQ** | Security posture | MCP-endpoint vulnerability scanning (SAFE-MCP). |
| **Sentry** | Monitoring | Error/perf monitoring on backend + client. |

> **Secrets** live only in `server/.env` / `client/.env` (gitignored) and the
> BAND daemon `agent_config.yaml`. Never commit keys. See `server/.env.example`
> for the full list.

---

## Verification scripts

The backend ships live diagnostics under `server/scripts/`:

- `check_keys.py` / `check_remaining_sponsors.py` — live connectivity for every provider.
- `verify_audio.py` — Deepgram STT↔TTS round-trip + YAMNet classification.
- `verify_app_hook.py` — drives the app→elder→caretaker BAND mesh end-to-end.
- `verify_emergency_call.py` — places a real gated emergency-dispatch call (to a number you control).
- `fetch_yamnet.py` — downloads the YAMNet model into `server/models/`.

Run the test suite with `python -m unittest discover -s tests` from `server/`.
