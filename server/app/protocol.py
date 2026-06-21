"""WebSocket protocol v1 models. Mirrors shared/protocol.md (read-only contract).

These are intentionally lenient on inbound parsing (extra fields ignored) and
strict on the shapes we emit.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

TriggerSource = Literal["fall", "audio_event", "scheduled", "manual"]
BackendState = Literal["idle", "checking_in", "escalating", "resolved"]


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


class AudioResponseMessage(BaseModel):
    type: Literal["audio_response"]
    elder_id: str
    ts: Optional[str] = None
    prompt_id: str
    audio_clip_b64: Optional[str] = None


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
        case "heartbeat":
            return HeartbeatMessage(**raw)
        case _:
            raise ValueError(f"unknown client message type: {msg_type!r}")
