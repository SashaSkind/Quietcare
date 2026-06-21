# Quietcare

An ambient AI safety companion for elderly care. **Cal Hacks 2026 · June 20–21 · Team: You + Sasha**

---

## Purpose / Problem

Elderly people living alone face a dangerous gap: when something goes wrong — a fall, a stroke, choking, sudden confusion — the people who could help often don't find out until far too late.

We want to contact the right people, whether it's you who lives a few minutes away, or a caretaker/doctor/ambulance who can act on the spot.

We asked the sponsors what they'd want for their own families, and the consensus was that the value comes from the **responsiveness** of the product — getting the right person looped in fast, without false alarms.

In one line:

> "Your phone doesn't blow up every time grandpa drops a spoon — only when something is actually wrong."

### Important notes (pitch / slides)
- Open on the problem: a statistic about elderly people living alone without timely help, then the case for urgency.
- Primary user is the **primary caretaker** — capable enough to set up the app and integrations. The product helps with reminders, fall tracking, medicine tracking, and logging observations.
- Identify the potential meaning behind trends in those logs, and surface suggestions toward the right kind of specialist.
- The caretaker's concrete tasks map directly onto the caretaker-agent's tool list (SMS, call, refill, request-911-confirmation).

Schedule: https://hive.hackberkeley.org/schedule

---

## Recruiting targets (separate from product integrations)

These are job opportunities to reach out about — **not** sponsors we're integrating. Kept distinct from the sponsor stack below so the two don't get confused (e.g. Terac and Poke appear here as employers, but are not in our product's runtime path).

- **MTS at Poke (Interaction Co):** https://jobs.ashbyhq.com/interaction/56b66af2-bce5-4ad7-baf9-ace14eb6a29a
- **FDE at Deepgram:** https://jobs.ashbyhq.com/Deepgram/c69aab8a-e1d5-44ac-9113-12671a364015
- **Marketing at Terac:** https://jobs.ashbyhq.com/terac/44bc7549-9ef3-4c4f-b55f-468aaa12ef55
  - Terac is an expert-marketplace / human-data company; their marketing is likely B2B (selling to AI labs + research firms), so frame any pitch around transferable skills. Have a one-line background hook ready before reaching out to Jack.

---

## Sponsors & how we use their products

Each sponsor below earns its place in a specific layer of the stack. The principle throughout: **match the tool to the job**, and don't add an integration just to chase a prize. Every integration below is wired behind an interface with an automatic **mock fallback**, so the whole system runs end-to-end with zero credentials.

> **Secrets:** all keys live in `server/.env` (and `client/.env`), never in this doc. See `server/.env.example` for the full list.

### Integrated and working

| Sponsor | Layer | How we use it (in code) |
| --- | --- | --- |
| **PaleBlueDot** (TokenRouter) | Inference | Anthropic-compatible gateway that **serves Claude** with free credits. The same Anthropic SDK client is pointed at the PBD base URL (`AnthropicLLM` in `server/app/providers/llm.py`), so tool-use / function-calling passes through unchanged. **Direct Anthropic is the verified fallback** — the swap is config, not redesign. (See `_build_llm` in `providers/factory.py`.) |
| **BAND** | Inter-agent bus | The message bus between the **elder-agent** and **caretaker-agent** (`BandBus` in `providers/bus.py`: REST `publish`, WS for streaming subscriptions, in-process fan-out fallback). Carries the core differentiator — noise-filtering escalation — and satisfies the ≥2-agents-collaborating requirement. Pro tier via code `BANDHACK26`. |
| **Deepgram** | Voice I/O | Real STT (`nova-2`) + TTS (`aura-asteria-en`, linear16 WAV) in `providers/voice.py`, powering the spoken check-in ladder ("Are you okay?" → listen → transcribe). All STT/TTS is server-side; the client only plays and records. |
| **Redis** | Agent memory | Elder profile, meds, history, and recent events via `RedisMemory` (`providers/memory.py`), seeded with a sample resident (Margaret, 78). Code `CALHACKER2026`. |
| **Twilio** | Emergency channel | Actually rings/texts the human caretaker (`TwilioTelephony`: `send_sms`, `call_voice`, gated `dispatch_emergency`). Kept on the critical path because it's direct and reaches any phone. Also powers the inbound "how's mom?" SMS recap and the 911-authorization text. *(Not a sponsor, but the right tool for the safety path.)* |
| **Sentry** | Monitoring | Error/perf monitoring on a safety-critical path. **Backend**: FastAPI integration + `capture()` around agent runs (`sentry_init.py`). **Client**: `@sentry/react-native` with WS/audio/camera breadcrumbs (raw audio/image payloads never sent). |
| **Browserbase** | Everyday-care automation | The non-emergency "refill meds / book the doctor" hand-off (`BrowserbaseBrowser` in `providers/browser.py`). Provisions a cloud session and drives the page over CDP with Playwright (navigate → click a refill/add-to-cart control → capture result), returning a replay URL the dashboard links to. **Always off the emergency critical path.** |
| **Arize AX** | Evals / tracing | OpenTelemetry tracing of the agent tool-use loop and every Claude call (`observability.py`, via `arize-otel` + OpenInference Anthropic auto-instrumentation). This is our **safety-standout** slot — proving the emergency classifier's behavior is observable and inspectable. |
| **ArmorIQ** | Security posture | MCP-endpoint vulnerability scanning (SAFE-MCP techniques) via `ArmorIQScanner` (`providers/security_scan.py`); surfaced on the dashboard's **Trust** tab and scanned at startup. *(Originally framed as "pick Arize OR ArmorIQ" — we shipped both, as a low-effort, non-blocking posture check rather than an inline gate.)* |

> **PaleBlueDot prize trade-off:** routing through a reseller may forfeit Anthropic's own prize — the code is model-agnostic so we can flip to the direct Anthropic key if we decide that relationship matters more.

### Might use — pick by time and prize strategy
- **Simular/Sai** — alternative to Browserbase for the booking task; gives the "operates it like a human" narrative but computer-use is more failure-prone. We're leaning Browserbase for demo safety. (Simular's prize needs a social post tagging them.)
- **Poke (Interaction Co)** — only as the ambient, **non-urgent** caretaker channel ("how's mom today?"), never the emergency path. *(We already ship an inbound-SMS recap over Twilio that covers this need; add Poke only if its API/MCP checks out and we want the prize.)*
- **Orkes, ElevenLabs, The Token Company** — optional polish (durable workflow orchestration, a warmer voice, prompt compression). Not integrated yet; add only with spare time.

### Skip (not a fit)
Fetch.ai (redundant with BAND + Web3 overhead), Midjourney/Pika (media gen, only if we add reminiscence), Overshoot (pulled out — replaced by Claude's native vision plan), RunPod (we're on hosted APIs), Terac (human-data/annotation, off the runtime path — but a recruiting target, see above), and the rest (Cognichip, QNX, Zoox, UFB, HRT, SkyDeck, House Fund, Context, Fieldguide) — no integration role.

---

## What we've actually built (status)

The build went **beyond** the original MVP. Current state:

- **Cloud backend** (`/server`, Python 3.11 + FastAPI): WS `/ws` ingest, the two Claude agents, the explicit escalation state machine, and REST endpoints powering the dashboard.
- **Two cooperating Claude agents** over BAND with full tool-use loops (tools listed below).
- **On-device client** (`/client`, Expo / React Native, Android dev build + web): real accelerometer fall detection (impact + stillness), rolling pre-event audio buffer, camera snapshot, check-in playback/record, resilient WebSocket with reconnect.
- **Caretaker dashboard** (`/dashboard`, React + Vite + TS + Tailwind + TanStack Query + Recharts): residents overview, Today recap, Wellness trends, Medications editor + adherence, History timeline, and a Trust tab (provider status + ArmorIQ scan).
- **Server-side audio-scene ML**: YAMNet (TFLite) and/or PANNs (CNN14) distress tagging (thud/scream/groan/glass), fused into the elder-agent's decision via `get_acoustic_evidence`.
- **Safety machinery**: explicit FSM, a local **policy gate** (0–100 risk scoring + kill-switch on `escalation`/`emergency_dispatch`), and **gated 911** requiring a one-time human-confirmation token.
- **Care features**: medication reminder scheduler + adherence logging, geofence/wandering + inactivity ("silent emergency") triggers, inbound caretaker SMS recap, per-device auth.

**Not yet wired:** Claude **vision** on the camera frame — `frame_b64` is captured by the client and carried in the protocol, but the elder-agent currently decides on acoustic + transcript signals only. Vision interpretation remains a stretch.

---

## MVP Definition (proven)

The smallest version that proves the whole value proposition — and it runs end-to-end with everything non-essential mocked:

1. Client captures mic + accelerometer (+ camera) and detects falls on-device; **Simulate Fall** remains a manual override.
2. On a trigger, the client streams the event + pre-event audio (+ a camera still) to the backend over the WebSocket.
3. **Elder-agent** (Claude + tool use) receives the event, transcribes via Deepgram, factors in acoustic-scene tags, and decides emergency vs. not.
4. Elder-agent messages the **caretaker-agent** over BAND (passing through the policy gate).
5. **Caretaker-agent** triages and, only on a real emergency, alerts the human via Twilio (SMS first, voice for high severity).
6. Redis holds the elder's profile / meds / history for context.

**Definition of done (met):** `python mock/send_trigger.py --scenario emergency` drives trigger → check-in → no clear response → BAND → caretaker → Twilio; `--scenario fine` resolves silently with no caretaker notification. The noise-filter contrast is demonstrable, and it all works in all-mock mode with no keys.

---

## User Flow

The elder wears the phone on a lanyard. The app listens (audio) continuously-but-cheaply and watches motion via the accelerometer; the camera fires only at trigger time.

1. A **trigger** fires — a detected fall (on-device threshold model), an audio event, a missed scheduled check-in, **inactivity** (possible silent emergency like a stroke), or **geofence** (left the safe zone / wandering). The **Simulate Fall** button is the manual override.
2. The **elder-agent** runs a voice check-in through Deepgram: "Are you okay?" and listens, pulling acoustic-scene tags on the clip.
3. If the response is clearly fine and there's no acoustic distress, it logs the event and stays silent — the caretaker is never bothered.
4. If there's no clear answer, distress is confirmed, or the audio shows a thud/scream with no reassuring reply, the elder-agent **escalates** to the caretaker-agent over BAND with a structured summary — **after** clearing the policy gate.
5. The **caretaker-agent** triages. For a real emergency it texts/calls the human via Twilio with a concise spoken summary. **911 remains a gated, human-confirmed last resort** — `request_911_confirmation` sends an authorization link/token; `escalate_911` is hard-gated and never autonomous.
6. Separately, for non-emergency needs ("I'm low on my blood-pressure meds"), the caretaker-agent hands off to **Browserbase** to refill on the relevant portal, and the dashboard surfaces the replay link.

---

## Teams & Data Flow

"Teams" here means the two cooperating agents. The design deliberately keeps them as a pair talking over BAND rather than collapsing into one worker — the two-agent conversation is the heart of the pitch.

- **Elder-agent** (cloud, Claude) — tools: `get_elder_profile`, `get_recent_events`, `speak_to_elder`, `listen_to_elder`, `get_acoustic_evidence`, `log_event`, `notify_caretaker_agent`. Ingests the event, runs the check-in, fuses signals, and decides whether to involve the caretaker.
- **Caretaker-agent** (cloud, Claude) — tools: `get_elder_profile`, `send_caretaker_sms`, `call_caretaker_voice`, `book_task`, `refill_medication` (Browserbase), `request_911_confirmation`, `escalate_911` (gated). Triages noise vs. emergency, alerts the human, and runs everyday-care errands.

**Data flow:** Phone sensors → on-device cheap trigger → stream event + clip (+ frame) to backend → Elder-agent (Deepgram transcribe + YAMNet/PANNs acoustic tags + Redis context) → **policy gate** → BAND → Caretaker-agent (triage) → Twilio to human / Browserbase for booking. Arize traces the whole loop; Sentry watches for errors.

**Key rule:** gate every expensive call (Claude, transcription) behind the cheap on-device detection. Never call Claude on every frame — only on the moments that matter. This protects cost, battery, privacy, and connectivity at once.

---

## Tech Stack

| Layer | Tool / Service |
| --- | --- |
| **Device client** | Expo / React Native (Android dev build; also runs on web). Accelerometer fall detection, rolling audio buffer, camera snapshot, check-in playback/record, resilient WebSocket. A native always-on wearable is the "production path." |
| **Caretaker dashboard** | React + Vite + TypeScript SPA · TailwindCSS · TanStack Query (polling) · Recharts · Lucide. Thin layer over the backend REST API; all safety logic stays server-side. |
| **AI model** | Claude (Anthropic) — multimodal reasoning + tool use; the brain of both agents. |
| **Inference** | PaleBlueDot TokenRouter (serving Claude, free credits) with the direct Anthropic API as the verified fallback. |
| **Agent runtime** | Anthropic Messages API tool-use loop (`agents/base.py`: decide → act → observe). BAND as the inter-agent bus; Redis as memory. |
| **Voice** | Deepgram (STT `nova-2` + TTS `aura-asteria-en`) for the check-in loop. ElevenLabs optional (not integrated). |
| **Audio-scene ML** | Server-side YAMNet (TFLite) and/or PANNs (CNN14) distress tagging, ensemble-capable, fused into the elder-agent decision. |
| **On-device triggers** | Accelerometer threshold fall detection (impact spike + stillness over a ~2.5 s sliding window @ ~50 Hz) with refractory cooldown. |
| **Telephony** | Twilio for caretaker SMS/voice, inbound SMS recap, and the gated emergency dispatch. |
| **Browser automation** | Browserbase (cloud session + Playwright over CDP) for the everyday-care refill/booking path. |
| **Safety / policy** | Explicit escalation FSM + local policy gate (risk scoring + kill-switch) + one-time-token 911 confirmation. |
| **Observability** | Arize AX (OTel + OpenInference) for agent/LLM traces; Sentry for error/perf (backend + client). |
| **Security** | ArmorIQ MCP posture scan (startup + on-demand from the Trust tab). |
| **Map / Place data** | Not used. Emergencies resolve to an address via reverse-geocoding, not a live map. |
| **Web search** | Not used in-product. Web automation for booking is Browserbase, not a search layer. |
| **Deployment** | Cloud backend hosting the two Claude agents + WebSocket ingest; dashboard served as a web app; client as a foregrounded app for the demo. Sentry wraps everything. |

---

## Key Technologies

- **Claude tool-use loop** — tools are JSON-schema functions; Claude decides which to call, our code executes and returns the result, repeat until done (`agents/base.py`, `agents/elder.py`, `agents/caretaker.py`).
- **BAND agent bus** — structured `caretaker.notify` messages between elder- and caretaker-agents; satisfies the ≥2-agents requirement.
- **Deepgram STT/TTS** — real-time listen-and-speak for the check-in ladder.
- **Redis (beyond caching)** — agent memory: profile, meds, history, recent events.
- **Audio-scene ML** — YAMNet + PANNs acoustic-event spotting (thud/scream/groan/glass) as a weak signal fused with semantic content.
- **Policy gate** — deterministic, in-code chokepoint that scores risk and can physically block escalation/emergency actions independent of the LLM.
- **Twilio** — real calls/SMS on stage for the escalation moment, plus the inbound caretaker recap.
- **Browserbase + Playwright** — drives a real pharmacy portal for the refill hand-off; returns a replayable session.
- **Arize + Sentry** — traces and error monitoring across the safety-critical path.
- **Claude vision** — *planned*: interpret the captured camera frame on a trigger (frame is already captured + transmitted; agent integration is a stretch).

---

## Architecture Overview

**Thin client, heavy cloud, event-driven.** Phones are weak on compute and battery, so reasoning, transcription, and audio analysis are offloaded — but the stream is **gated, not continuous**.

**Phone (thin client):**
- Captures mic + camera + accelerometer.
- Runs cheap always-on triggers (on-device fall detection + a rolling audio buffer).
- On a trigger or scheduled check-in, streams the relevant clip + frame + event upward.
- Plays back voice responses and handles the talk-to-the-elder UI.

**Cloud — Elder-agent (Claude):**
- Receives events, transcribes (Deepgram), pulls acoustic-scene tags, fuses signals, decides whether to loop in the caretaker, and publishes over BAND (through the policy gate).

**Cloud — Caretaker-agent (Claude):**
- Receives BAND messages, triages, alerts the human via Twilio on real emergencies, requests gated 911 authorization, and invokes Browserbase for non-emergency booking.

**Caretaker dashboard (web):**
- Read-mostly view over the backend REST API: status, recap, wellness trends, medication schedule + adherence, history, and the human-in-the-loop 911 confirmation.

**Cross-cutting:** Redis for memory, the policy gate + FSM for safety, Arize for traces, Sentry for monitoring, ArmorIQ for security posture.

---

## Design Choices

- **Event-driven, not always-streaming.** An always-on chest camera/mic piping to the cloud is bad on privacy, battery, cost, and connectivity. Cheap detection stays local; only the interesting moments go up.
- **The LLM never autonomously calls 911.** It's legally/ethically wrong and technically hard. We built an escalation ladder with 911 as a gated, human-confirmed last resort: `request_911_confirmation` alerts a human with a one-time token; `escalate_911` is hard-gated in the FSM.
- **Defense in depth on escalation.** Beyond the LLM's judgment, a deterministic **policy gate** scores risk and can physically block escalation/emergency actions — the model can't fire them if policy says no.
- **Claude is the brain; Browserbase is a specialized hand.** Computer-use agents are slow and failure-prone — wrong for a real-time safety loop. We reserve Browserbase for the one GUI task with no clean API (booking) and call APIs directly everywhere else.
- **Two agents, not one.** The caretaker-agent that filters noise is the differentiator. Collapsing to a single notifier loses both the pitch and the clean BAND use.
- **Not a medical device.** Position it as a triage signal that decides whether to check in and escalate, with the person and caretaker as the real decision-makers — never diagnosis.
- **Compose the emergency signal, don't chase one magic model.** Layer acoustic events (YAMNet/PANNs) + semantic content (Deepgram → Claude) + trigger source, with Claude as the fusion layer outputting a decision and recommended action.

---

## Work Delegation / Team Split

Team: **You + Sasha**, building with **Devin** as an implementation accelerator (not a designer — feed it the tool contracts and data flow verbatim, one component at a time, and review between each).

| Owner | Responsibility |
| --- | --- |
| **You** | Architecture + the agent layer: Claude tool-use loops, the elder/caretaker system prompts, emergency-vs-not criteria, the policy gate, BAND wiring, and the PaleBlueDot tool-use verification. Keep the judgment-heavy logic in your own hands. |
| **Sasha** | The thin client + sensor/trigger pipeline: mic/accelerometer capture, on-device fall detection + Simulate Fall, streaming to the backend, voice playback UI, camera snapshot. |
| **Devin** | Implementation of well-specified components: provider scaffolding, Redis/Twilio/Deepgram/Browserbase integrations, the dashboard, glue code. Delegate decomposed tasks; don't let it design the agent prompts or escalation criteria. |
| **Shared** | The hero demo scene and the noise-filter contrast — rehearse and harden together; this is the pitch. |

---

## Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Tool-use doesn't pass cleanly through PaleBlueDot's router | Verified function-calling through PBD; code stays model-agnostic so falling back to direct Anthropic is config, not redesign (`_build_llm`). |
| Scope creep — too many integrations for 24h | Spine is locked (Claude + BAND + Deepgram + Redis + Twilio + Sentry) and proven; everything else degrades to a mock, so a missing key never blocks the demo. |
| Browser suspends background tabs / app backgrounding breaks capture | Keep the app foregrounded for the demo; cite the native wearable as the production path. |
| False positives from phone-based detection | The voice check-in before any escalation makes a false positive harmless; a buffer/voting window reduces noise; the policy gate adds a second guard. |
| Vocal-distress detection is unreliable | Treat prosody/acoustics as a weak secondary signal; lean on acoustic events + semantic content, with Claude as the fusion layer. |
| Devin builds the wrong thing if under-specified | Feed it exact tool contracts and data flow, one component at a time; review between each. Never delegate the agent prompts or escalation criteria. |
| Emergency path depends on a flaky consumer assistant | Twilio (not Poke) stays on the critical path; Poke/ambient is non-urgent only. |
| Secrets leaked in shared docs | Keys live in `.env` / a secrets manager, never in this doc. Rotate any key that's ever been pasted into a shared file. |

---

## Stretch Goals

**Done (was stretch):**
- Real on-device fall detection (accelerometer threshold model) replacing the button-only flow.
- Server-side acoustic distress ML (YAMNet + PANNs), fused into the decision.
- Booking/refill hand-off via Browserbase (with a replay link in the dashboard).
- Arize evals/tracing for the agent loop (safety standout) — and ArmorIQ posture scanning.
- Caretaker dashboard, medication reminders/adherence, geofence + inactivity triggers, inbound caretaker SMS.

**Still open:**
- Claude-vision interpretation of the camera frame on a trigger.
- Warmer voice via ElevenLabs; durable workflow orchestration via Orkes.
- Token Company prompt compression if medical-history context grows large.

---

## Demo Script (3 minutes)

Build toward one hero scene that shows the entire value prop back-to-back.

1. **Setup (~30s):** Introduce the lanyard phone and the one-line pitch — it stays silent through daily noise and only reaches out in a real emergency. Glance at the dashboard: "is mom okay?" at a glance.
2. **The noise-filter case (~45s):** The elder drops a cup. The elder-agent notes it (acoustic tag = clatter, elder says "I'm fine"), the caretaker-agent stays silent — no alert. This proves the filter that makes it a product.
3. **The emergency case (~60s):** The elder falls and says "I can't get up." The elder-agent checks in via Deepgram, gets no good response (with a thud in the audio), and escalates over BAND. The caretaker-agent calls/texts the human via Twilio (live, on stage) with a concise spoken summary.
4. **The ambient-care moment (~30s):** Show the caretaker-agent using Browserbase to refill the meds it learned were low — and the dashboard's "Watch the agent" replay — widening the story from alarm to everyday care assistant.
5. **Close (~15s):** Restate the differentiator and the safety framing — a triage signal with humans in the loop (gated 911, policy gate), not a medical device — and name the production path (native app, Apple Watch fall API).

Rehearse the contrast in steps 2–3 until it's flawless. Judges remember "it called grandma and caught that she sounded confused," not a feature list.
