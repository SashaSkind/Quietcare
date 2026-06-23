"""WebSocket protocol v1 models. Mirrors shared/protocol.md (read-only contract).

These are intentionally lenient on inbound parsing (extra fields ignored) and
strict on the shapes we emit.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

TriggerSource = Literal[
    "fall",
    "audio_event",
    "scheduled",
    "manual",
    "inactivity",  # no expected motion (possible silent emergency, e.g. stroke)
    "geofence",  # left a safe zone / wandering (dementia)
]
BackendState = Literal["idle", "checking_in", "escalating", "resolved"]


class GeoPoint(BaseModel):
    lat: float
    lng: float


# ---- CLIENT -> BACKEND ----
class DeviceState(BaseModel):
    battery: float = 1.0
    connectivity: str = "unknown"


class RegisterMessage(BaseModel):
    type: Literal["register"]
    elder_id: str
    device_token: Optional[str] = None


class TriggerMessage(BaseModel):
    type: Literal["trigger"]
    elder_id: str
    device_token: Optional[str] = None
    ts: Optional[str] = None
    trigger_source: TriggerSource = "manual"
    audio_clip_b64: Optional[str] = None
    frame_b64: Optional[str] = None
    device_state: DeviceState = Field(default_factory=DeviceState)
    # Optional context for non-fall triggers (inactivity/geofence): a short
    # human note and/or the device location at trigger time.
    note: Optional[str] = None
    location: Optional[GeoPoint] = None


class AudioResponseMessage(BaseModel):
    type: Literal["audio_response"]
    elder_id: str
    ts: Optional[str] = None
    prompt_id: str
    audio_clip_b64: Optional[str] = None
    transcript: Optional[str] = None


class AudioProbeMessage(BaseModel):
    type: Literal["audio_probe"]
    elder_id: str
    device_token: Optional[str] = None
    ts: Optional[str] = None
    audio_clip_b64: str


class VoiceConversationMessage(BaseModel):
    type: Literal["voice_conversation"]
    elder_id: str
    device_token: Optional[str] = None
    ts: Optional[str] = None
    transcript: str


class HeartbeatMessage(BaseModel):
    type: Literal["heartbeat"]
    elder_id: str
    ts: Optional[str] = None
    device_state: DeviceState = Field(default_factory=DeviceState)


# ---- BACKEND -> CLIENT ----
class SpeakMessage(BaseModel):
    type: Literal["speak"] = "speak"
    prompt_id: str
    audio_b64: str
    text: Optional[str] = None


class ListenMessage(BaseModel):
    type: Literal["listen"] = "listen"
    prompt_id: str
    duration_ms: int


class StatusMessage(BaseModel):
    type: Literal["status"] = "status"
    state: BackendState


class AckMessage(BaseModel):
    type: Literal["ack"] = "ack"
    received: str


class AudioProbeResultMessage(BaseModel):
    type: Literal["audio_probe_result"] = "audio_probe_result"
    elder_id: str
    transcript: str
    wants_attention: bool
    audio_scene: dict[str, Any]


class VoiceConversationReplyMessage(BaseModel):
    type: Literal["voice_conversation_reply"] = "voice_conversation_reply"
    elder_id: str
    action: str
    transcript: str
    reply_text: str
    audio_b64: str
    escalation: Optional[Any] = None


def parse_client_message(raw: dict[str, Any]) -> BaseModel:
    """Parse an inbound client frame into the appropriate model."""
    msg_type = raw.get("type")
    match msg_type:
        case "register":
            return RegisterMessage(**raw)
        case "trigger":
            return TriggerMessage(**raw)
        case "audio_response":
            return AudioResponseMessage(**raw)
        case "audio_probe":
            return AudioProbeMessage(**raw)
        case "voice_conversation":
            return VoiceConversationMessage(**raw)
        case "heartbeat":
            return HeartbeatMessage(**raw)
        case _:
            raise ValueError(f"unknown client message type: {msg_type!r}")
