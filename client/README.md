# Quietcare — Client

Device-side Expo app for **Quietcare**, an always-on elderly-safety companion. The
app listens to motion + audio cheaply and, when something looks wrong, streams a
short event to the cloud backend over a WebSocket (protocol v1, see
`../shared/protocol.md`).

> This folder is the **client only**. The backend (AI agents, Deepgram, Twilio,
> Redis) lives in `/server` and is built separately behind the WebSocket contract.
> The client holds **no API keys**.

## Features

- **One screen:** large status banner (*All good* / *Checking in…* / *Alerting
  caretaker…*), a big **Simulate Fall** button, and a scrolling debug log.
- **Resilient WebSocket client:** sends `register` on connect, `heartbeat` every
  30s, auto-reconnects with exponential backoff, logs every message in/out.
- **Simulate Fall** → sends a valid `trigger` (`trigger_source: "manual"`) with a
  bundled sample WAV as `audio_clip_b64`.
- **Check-in flow:** handles `speak` (plays audio via `expo-av`) then `listen`
  (records the mic for `duration_ms` and replies with `audio_response` carrying
  the same `prompt_id`).
- **Accelerometer:** subscribes via `expo-sensors` at ~50 Hz, computes signal
  magnitude, streams it to the debug log. A stubbed `detectFall()` always returns
  `false` for now (real TFLite model comes later). Simulate Fall bypasses it.
- **Sentry:** crash/error reporting via `@sentry/react-native`, with breadcrumbs
  for WebSocket + audio events. Raw audio payloads are never sent to Sentry.

## Stack

Expo (managed, TypeScript) targeting a **development build** (native audio +
on-device ML need more than Expo Go). `expo-sensors`, `expo-av`,
`expo-file-system`, `@sentry/react-native`, native WebSocket API. Demo target:
**Android**.

## Prerequisites

- Node 18+ and npm
- For the dev build: Android Studio + an emulator or a physical Android device,
  and an [Expo account](https://expo.dev) for EAS (`npm i -g eas-cli`).

## Setup

```bash
cd client
npm install
cp .env.example .env   # adjust EXPO_PUBLIC_WS_URL if needed
```

`.env` values:

| Variable | Purpose |
| --- | --- |
| `EXPO_PUBLIC_WS_URL` | Backend WebSocket URL incl. `/ws`. For the mock on a device, use your LAN IP (e.g. `ws://192.168.1.50:8080/ws`). |
| `EXPO_PUBLIC_SENTRY_DSN` | Sentry **client** DSN (a DSN is not a secret). |
| `EXPO_PUBLIC_ELDER_ID` | Elder identifier this device represents. |

> The sample audio clip is generated at `src/assets/sampleAudio.ts`. Regenerate
> with `npm run gen:audio` if needed.

## Run the mock backend (standalone testing)

The mock is a throwaway test harness (the one exception to "client only"):

```bash
cd client/mock
npm install
npm start            # ws://0.0.0.0:8080/ws
```

It accepts `register`/`trigger`, replies with `speak` then `listen`, prints the
received `audio_response`, and sends `status` updates.

## Run the client (dev build)

```bash
cd client

# 1) Create a development build (first time / when native deps change)
eas build --profile development --platform android
#   install the resulting .apk on your emulator/device, OR run locally:
#   npx expo run:android   (requires local Android toolchain)

# 2) Start the dev server and open the dev build
npm start            # then press 'a' for Android, or scan in the dev build
```

Point `EXPO_PUBLIC_WS_URL` at the mock (or the real backend once it exists).

## Verify (Definition of Done)

With the mock running and the client open:

1. Press **Simulate Fall** → debug log shows an outgoing `trigger`.
2. Client plays the `speak` audio, records for `duration_ms`, and returns an
   `audio_response` with the matching `prompt_id` (mock prints it).
3. Accelerometer magnitude streams into the debug log (~1 line/sec).
4. Kill/restart the mock → the client reconnects with backoff.

### Sentry smoke test

Temporarily add `captureException(new Error('sentry smoke test'))` somewhere on
mount, confirm it lands in the Sentry **client** project, then remove it. Also
set `organization` / `project` in the `@sentry/react-native/expo` plugin block in
`app.json` to enable native symbolication/source maps.

## Project layout

```
client/
  App.tsx                  # root component (wrapped with Sentry)
  index.ts                 # entry point
  app.json, eas.json       # Expo + EAS dev-build config
  scripts/gen-audio.js     # regenerates the bundled sample WAV
  mock/                    # throwaway ws test backend
  src/
    config.ts              # env-driven config
    types.ts               # protocol v1 message types
    sentry.ts              # Sentry init + helpers
    ws/WebSocketClient.ts  # resilient socket (register/heartbeat/reconnect)
    audio/audioManager.ts  # play + record (expo-av + expo-file-system)
    sensors/               # accelerometer monitor + detectFall stub
    components/            # StatusBanner, DebugLog
    hooks/useQuietcare.ts  # orchestration
    assets/sampleAudio.ts  # generated base64 WAV
```

## Out of scope

Agents, LLM calls, Deepgram, Twilio, Redis, real fall-detection ML, the caretaker
side, anything in `/server`.

## CHANGELOG

### 0.1.0
- Initial client scaffold: single-screen UI (status banner, Simulate Fall,
  debug log).
- WebSocket client with `register`, 30s `heartbeat`, backoff reconnect, full
  in/out logging.
- Simulate Fall → `trigger` with bundled sample WAV.
- `speak` playback + `listen` record → `audio_response` (echoes `prompt_id`).
- Accelerometer @ ~50 Hz with magnitude logging and stubbed `detectFall()`.
- Sentry integration (`@sentry/react-native`) with WS/audio breadcrumbs.
- Mock ws backend for standalone testing.
