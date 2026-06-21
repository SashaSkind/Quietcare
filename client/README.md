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
- **On-device fall detection:** `expo-sensors` accelerometer at ~50 Hz feeds a
  threshold detector (`detectFall`) that looks for an **impact spike** followed
  by a **stillness window** across a ~2.5 s sliding buffer. A detected fall fires
  the same trigger path with `trigger_source: "fall"`; a refractory cooldown
  prevents repeat triggers. Thresholds live in `FALL_DETECTION` in
  `src/config.ts`.
- **Simulate Fall** stays as a **manual override** → `trigger` with
  `trigger_source: "manual"`, bypassing the detector.
- **Rolling audio buffer (always-on = buffer, not upload):** the mic
  continuously records short segments into an on-device ring buffer. When a
  trigger fires, the **preceding** seconds of audio are sent as `audio_clip_b64`
  — not silence captured after the fact. Configurable via `AUDIO_BUFFER`.
- **Check-in flow:** handles `speak` (plays audio via `expo-av`) then `listen`
  (records the mic for `duration_ms` and replies with `audio_response` carrying
  the same `prompt_id`). The buffer is paused during playback/listen and resumed
  after (the mic is shared).
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

## Build & install on Android (EAS development build)

Expo Go is **not** enough — native audio capture, the rolling buffer, and
on-device sensors need a custom **development build**. Steps to get one onto a
real Android device:

```bash
cd client
npm install
npm install -g eas-cli        # if not already installed

# 1) Log in to your Expo account (creates the cloud build).
eas login
eas whoami                    # confirm you're logged in

# 2) Link this project to an EAS project (writes extra.eas.projectId in app.json).
eas init                      # accept creating/selecting a project

# 3) Kick off the Android development build (cloud build, ~10-20 min).
eas build --profile development --platform android
```

When the build finishes, the CLI prints a URL (also on https://expo.dev under
your project → Builds).

**Install the APK on an Android phone (any of these):**

- **Easiest:** open the build URL on the phone (or scan the QR the CLI shows) and
  tap **Install**. Approve "install from unknown sources" if prompted.
- **Via adb (USB):** download the `.apk`, enable USB debugging on the phone, then
  `adb install ./your-build.apk`.
- **Emulator:** drag the `.apk` onto a running Android emulator window, or
  `adb install` it.

**Run it against the dev server:**

```bash
cd client
npm start                     # Metro for the dev build (expo start --dev-client)
```

Open the installed **Quietcare (dev)** app on the phone; it connects to Metro
(same Wi-Fi). On first launch, **grant microphone permission** — the rolling
audio buffer needs it.

> **Local alternative (no EAS account):** with Android Studio + SDK installed,
> `npx expo run:android` builds and installs a dev build directly from your
> machine.

### Verifying native audio + background-style capture on the device

1. Grant mic permission; watch the debug log for `accel |a|` lines (~1/sec).
2. With the mock backend reachable (set `EXPO_PUBLIC_WS_URL` to your LAN IP),
   press **Simulate Fall**. The log should say it's sending **buffered
   pre-event audio** (non-trivial byte count), and the mock prints an
   `audio_response`.
3. **Real fall test:** with the phone in hand, sharply drop-and-rest it on a
   cushion (a hard impact followed by stillness). The detector should log
   `FALL DETECTED` and fire a `fall` trigger. Tune sensitivity via
   `FALL_DETECTION` in `src/config.ts`.

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
    audio/audioManager.ts  # mic owner: rolling buffer + play + record
    sensors/               # accelerometer monitor + threshold detectFall
    components/            # StatusBanner, DebugLog
    hooks/useQuietcare.ts  # orchestration
    assets/sampleAudio.ts  # generated base64 WAV
```

## Out of scope

Agents, LLM calls, Deepgram, Twilio, Redis, real fall-detection ML, the caretaker
side, anything in `/server`.

## CHANGELOG

### 0.2.0
- Real on-device **fall detection**: threshold algorithm (impact spike +
  stillness over a ~2.5 s sliding window @ 50 Hz) with a refractory cooldown;
  detected falls fire `trigger_source: "fall"`. Simulate Fall remains a manual
  override. Tunables in `FALL_DETECTION` (`src/config.ts`).
- **Rolling audio buffer**: the mic continuously records short segments into an
  on-device ring buffer; triggers now send the *preceding* seconds of audio
  instead of post-event silence. `AudioManager` serializes mic access (buffer
  pauses during playback/listen). Tunables in `AUDIO_BUFFER`.
- README: full EAS development-build + Android install + device-verification
  steps.

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
