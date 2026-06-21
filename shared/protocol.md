# Quietcare — WebSocket Protocol v1 (shared contract)

> **Read-only reference for both `/client` and `/server`.** If this needs to
> change, stop and coordinate — editing it breaks the other half.

Client opens a WebSocket to the backend at `/ws`. Every message is a JSON text
frame with a `type` field. All audio is base64-encoded WAV or Opus.

## CLIENT → BACKEND

```json
{ "type": "register", "elder_id": "margaret-01" }

{
  "type": "trigger",
  "elder_id": "margaret-01",
  "ts": "2026-06-20T18:30:00Z",
  "trigger_source": "fall" | "audio_event" | "scheduled" | "manual" | "inactivity" | "geofence",
  "audio_clip_b64": "<base64 audio ~3-5s, or null>",
  "frame_b64": "<base64 jpeg, or null>",
  "device_state": { "battery": 0.82, "connectivity": "wifi" },
  "note": "<optional short human note, e.g. 'left safe zone'>",
  "location": { "lat": 37.7749, "lng": -122.4194 }
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

## BACKEND → CLIENT

```json
{ "type": "speak", "prompt_id": "p1", "audio_b64": "<base64 audio>", "text": "Margaret, are you okay?" }

{ "type": "listen", "prompt_id": "p1", "duration_ms": 6000 }

{ "type": "status", "state": "idle" | "checking_in" | "escalating" | "resolved" }

{ "type": "ack", "received": "trigger" }
```

## Rules both sides obey

- A check-in is always: backend sends `speak`, then `listen`; client plays the
  audio, records `duration_ms`, replies with `audio_response` carrying the same
  `prompt_id`.
- **All STT/TTS happens on the backend** (Deepgram). The client only plays and
  records audio — it never transcribes or synthesizes.
- **The client holds NO API keys.** Anthropic, Deepgram, Twilio, BAND, Redis live
  on the backend only.
- The WebSocket URL is configurable on the client via `EXPO_PUBLIC_WS_URL`.
