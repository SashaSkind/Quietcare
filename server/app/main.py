"""FastAPI app: GET /health and WS /ws implementing the protocol v1 server side."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from typing import Optional

from fastapi import (
    FastAPI,
    Form,
    Header,
    HTTPException,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .auth import provision_device, verify_device
from .caretaker_query import (
    handle_inbound_sms,
    prompt_elder_to_call,
    summarize_for_caretaker,
)
from .config import settings
from .confirmations import ConfirmationRegistry
from .medications import (
    MedicationService,
    adherence_summary,
    run_medication_reminder,
)
from .elder_conversation import handle_elder_conversation, wants_attention
from .escalation_flow import call_caretaker_with_emergency_fallback
from .observability import init_tracing
from .wellness import summarize_wellness
from .protocol import (
    AudioProbeMessage,
    AudioProbeResultMessage,
    AudioResponseMessage,
    RegisterMessage,
    TriggerMessage,
    VoiceConversationMessage,
    VoiceConversationReplyMessage,
    parse_client_message,
)
from .providers.factory import build_providers
from .sentry_init import capture, init_sentry
from .session import (
    CaretakerService,
    ElderSession,
    SessionRegistry,
    confirm_911,
    handle_trigger,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("quietcare.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_sentry()
    # Enable Arize tracing before the Anthropic client is constructed so the
    # OpenInference instrumentation patches are in place for all LLM calls.
    init_tracing()
    providers = build_providers(settings)

    # Seed elder profile into real Redis if it's empty (no-op for mock memory,
    # which seeds itself; idempotent for Redis via seed()'s existence check).
    seed = getattr(providers.memory, "seed", None)
    if seed is not None:
        try:
            await seed()
        except Exception as exc:  # pragma: no cover - external store
            logger.warning("memory seed failed (%s); continuing", exc)

    registry = SessionRegistry()
    confirmations = ConfirmationRegistry()
    caretaker = CaretakerService(
        providers,
        registry,
        confirmations,
        auto_emergency_fallback=settings.auto_emergency_fallback,
        caretaker_ack_timeout_seconds=settings.caretaker_ack_timeout_seconds,
    )
    caretaker.attach()

    medications = MedicationService(providers, registry, settings)

    app.state.providers = providers
    app.state.registry = registry
    app.state.confirmations = confirmations
    app.state.caretaker = caretaker
    app.state.medications = medications
    app.state.bg_tasks = set()
    logger.info("Quietcare backend up. providers=%s", providers.summary())

    # Best-effort ArmorIQ posture scan of configured MCP endpoints at startup.
    for target in settings.scan_target_list:
        try:
            res = await providers.security_scan.scan(target)
            level = "warning" if res.severity_level not in ("safe", "unknown") else "info"
            getattr(logger, level)(
                "ArmorIQ scan %s: severity=%s score=%s mcp_endpoints=%s",
                target, res.severity_level, res.vulnerability_score, res.mcp_endpoints,
            )
        except Exception as exc:  # pragma: no cover - external
            logger.warning("startup security scan failed for %s (%s)", target, exc)

    # Background medication-reminder scheduler.
    med_task = asyncio.create_task(medications.run_forever())
    app.state.bg_tasks.add(med_task)
    yield
    med_task.cancel()
    logger.info("Quietcare backend shutting down.")


app = FastAPI(title="Quietcare Backend", version="0.1.0", lifespan=lifespan)

# Permit cross-origin calls from the in-app caretaker dashboard / web preview.
# Dev-only wide-open policy; tighten for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, object]:
    providers = getattr(app.state, "providers", None)
    return {
        "status": "ok",
        "providers": providers.summary() if providers else {},
    }


class Confirm911Request(BaseModel):
    token: str
    approve: bool = True


@app.get("/incidents/{elder_id}/confirmation")
async def get_confirmation(elder_id: str) -> dict[str, object]:
    """Return the pending 911 confirmation status for an elder (no token)."""
    confirmations: ConfirmationRegistry = app.state.confirmations
    pc = confirmations.get(elder_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="no confirmation for elder")
    return {"elder_id": elder_id, "status": pc.status, "reason": pc.reason}


@app.post("/incidents/{elder_id}/confirm_911")
async def post_confirm_911(elder_id: str, body: Confirm911Request) -> dict[str, object]:
    """Human approves/rejects emergency dispatch. The hard gate (token + FSM)
    is enforced inside confirm_911."""
    try:
        return await confirm_911(
            registry=app.state.registry,
            confirmations=app.state.confirmations,
            providers=app.state.providers,
            elder_id=elder_id,
            token=body.token,
            approve=body.approve,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="no pending confirmation")
    except PermissionError:
        raise HTTPException(status_code=403, detail="invalid confirmation token")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


class ElderCreate(BaseModel):
    elder_id: str
    name: str
    age: Optional[int] = None
    medications: list[str] = []
    conditions: list[str] = []
    prior_falls: int = 0
    notes: str = ""
    caretaker: dict = {}


def _check_admin(token: Optional[str]) -> None:
    """Guard provisioning endpoints when an ADMIN_TOKEN is configured."""
    if settings.admin_token and token != settings.admin_token:
        raise HTTPException(status_code=401, detail="admin token required")


@app.post("/elders")
async def create_elder(
    body: ElderCreate, x_admin_token: Optional[str] = Header(default=None)
) -> dict[str, object]:
    """Provision an elder profile + a one-time device token (shown once)."""
    _check_admin(x_admin_token)
    memory = app.state.providers.memory
    if await memory.get_profile(body.elder_id) is not None:
        raise HTTPException(status_code=409, detail="elder already exists")
    profile = body.model_dump()
    await memory.set_profile(body.elder_id, profile)
    token = await provision_device(memory, body.elder_id)
    return {"elder_id": body.elder_id, "device_token": token, "profile": profile}


@app.get("/elders")
async def list_elders() -> dict[str, object]:
    elders = await app.state.providers.memory.list_elders()
    return {"elders": elders}


@app.get("/elders/{elder_id}")
async def get_elder(elder_id: str) -> dict[str, object]:
    profile = await app.state.providers.memory.get_profile(elder_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="elder not found")
    # Never expose the device token via the read API.
    return {"elder_id": elder_id, "profile": profile}


@app.get("/elders/{elder_id}/events")
async def get_elder_events(
    elder_id: str, kind: Optional[str] = None, limit: int = 50
) -> dict[str, object]:
    """Return the elder's logged event/incident history (most recent last).

    Optional ``kind`` filter (e.g. ``incident``) and ``limit`` for the tail.
    """
    events = await app.state.providers.memory.get_events(elder_id)
    if kind:
        events = [e for e in events if isinstance(e, dict) and e.get("kind") == kind]
    if limit and limit > 0:
        events = events[-limit:]
    return {"elder_id": elder_id, "count": len(events), "events": events}


@app.get("/elders/{elder_id}/summary")
async def get_elder_summary(
    elder_id: str, question: str = "How is she doing today?"
) -> dict[str, object]:
    """Natural-language "warm update" for the caretaker — the same recap the
    inbound-SMS channel sends, exposed for dashboards/apps. Read-only."""
    providers = app.state.providers
    if await providers.memory.get_profile(elder_id) is None:
        raise HTTPException(status_code=404, detail="elder not found")
    summary = await summarize_for_caretaker(providers, elder_id, question)
    return {"elder_id": elder_id, "question": question, "summary": summary}


def _twiml(message: str) -> Response:
    """Build a TwiML SMS reply (Twilio sends `message` back to the texter)."""
    escaped = (
        message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    xml = f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{escaped}</Message></Response>"
    return Response(content=xml, media_type="application/xml")


@app.post("/twilio/sms")
async def twilio_inbound_sms(
    Body: str = Form(default=""),
    From: str = Form(default=""),
) -> Response:
    """Inbound caretaker SMS ("how's mom today?"). Resolves the elder from the
    sender's number, generates a warm recap from profile + recent incidents, and
    replies via TwiML. Read-only; off the emergency path."""
    providers = app.state.providers
    body = Body.strip() or "How is she doing?"
    try:
        reply = await handle_inbound_sms(providers, app.state.registry, From, body)
        return _twiml(reply)
    except Exception as exc:
        capture(exc, where="twilio_inbound_sms", sender=From)
        logger.exception("inbound sms failed: %s", exc)
        return _twiml("Sorry, I couldn't pull an update right now. Please try again shortly.")


class ScanRequest(BaseModel):
    url: str


@app.post("/admin/security-scan")
async def security_scan(
    body: ScanRequest, x_admin_token: Optional[str] = Header(default=None)
) -> dict[str, object]:
    """Run an ArmorIQ MCP vulnerability scan against an MCP endpoint URL and
    return the vulnerability score + severity. Guarded by ADMIN_TOKEN."""
    _check_admin(x_admin_token)
    result = await app.state.providers.security_scan.scan(body.url)
    return result.to_dict()


class RefillRequest(BaseModel):
    medication: str
    pharmacy_url: Optional[str] = None


@app.post("/elders/{elder_id}/refill")
async def refill_medication(elder_id: str, body: RefillRequest) -> dict[str, object]:
    """Everyday-care errand: hand a prescription refill to the browser provider
    (Browserbase). Off the emergency critical path."""
    providers = app.state.providers
    if await providers.memory.get_profile(elder_id) is None:
        raise HTTPException(status_code=404, detail="elder not found")
    res = await providers.browser.run_task(
        f"Refill prescription: {body.medication}",
        {"elder_id": elder_id, "pharmacy_url": body.pharmacy_url},
    )
    return {"elder_id": elder_id, "task": res.to_dict()}


# ---- Medication reminders + adherence ----------------------------------------

class MedicationItem(BaseModel):
    name: str
    time: str  # "HH:MM"
    dose: Optional[str] = None


class MedicationSchedule(BaseModel):
    medications: list[MedicationItem]


async def _require_elder(elder_id: str):
    providers = app.state.providers
    if await providers.memory.get_profile(elder_id) is None:
        raise HTTPException(status_code=404, detail="elder not found")
    return providers


@app.get("/elders/{elder_id}/medications")
async def get_medications(elder_id: str) -> dict[str, object]:
    providers = await _require_elder(elder_id)
    meds = await providers.memory.get_medications(elder_id)
    return {"elder_id": elder_id, "medications": meds}


@app.put("/elders/{elder_id}/medications")
async def set_medications(
    elder_id: str, body: MedicationSchedule,
    x_admin_token: Optional[str] = Header(default=None),
) -> dict[str, object]:
    _check_admin(x_admin_token)
    providers = await _require_elder(elder_id)
    meds = [m.model_dump() for m in body.medications]
    await providers.memory.set_medications(elder_id, meds)
    return {"elder_id": elder_id, "medications": meds}


@app.post("/elders/{elder_id}/medications/remind")
async def remind_medication_now(elder_id: str, body: MedicationItem) -> dict[str, object]:
    """Trigger a medication reminder immediately (manual/testing). Requires a
    connected device; otherwise logs a missed dose."""
    providers = await _require_elder(elder_id)
    session = app.state.registry.get(elder_id)
    if session is None:
        raise HTTPException(status_code=409, detail="elder device not connected")
    event = await run_medication_reminder(
        session, body.model_dump(), settings.med_confirm_window_ms
    )
    return {"elder_id": elder_id, "event": event}


@app.get("/elders/{elder_id}/adherence")
async def get_adherence(elder_id: str) -> dict[str, object]:
    providers = await _require_elder(elder_id)
    events = await providers.memory.get_events(elder_id)
    return {"elder_id": elder_id, "adherence": adherence_summary(events)}


# ---- Wellness trends + call bridge -------------------------------------------

@app.get("/elders/{elder_id}/wellness")
async def get_wellness(elder_id: str, days: int = 7) -> dict[str, object]:
    """Weekly wellness trend + warm summary for the caretaker."""
    await _require_elder(elder_id)
    return await summarize_wellness(app.state.providers, elder_id, days)


@app.post("/elders/{elder_id}/call-bridge")
async def call_bridge(elder_id: str) -> dict[str, object]:
    """Two-way bridge: prompt the elder (over the voice loop) to call their
    caretaker. Returns whether a connected, idle device was reached."""
    providers = await _require_elder(elder_id)
    profile = await providers.memory.get_profile(elder_id) or {}
    caretaker_name = (profile.get("caretaker") or {}).get("name", "")
    ok = await prompt_elder_to_call(app.state.registry, elder_id, caretaker_name)
    return {"elder_id": elder_id, "prompted": ok}


class TranscribeRequest(BaseModel):
    audio_clip_b64: Optional[str] = None


@app.post("/voice/transcribe")
async def transcribe_clip(body: TranscribeRequest) -> dict[str, object]:
    """Transcribe a base64 audio clip via the configured voice provider
    (Deepgram when live, mock otherwise). Used by the on-device hybrid check-in
    to hear the elder's spoken response without the full WS/FSM session."""
    transcript = await app.state.providers.voice.transcribe(body.audio_clip_b64)
    return {"transcript": transcript}


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    app.state.bg_tasks.add(task)
    task.add_done_callback(app.state.bg_tasks.discard)


async def _authorized(websocket: WebSocket, msg) -> bool:
    """Enforce per-device auth when enabled. Returns False (and notifies the
    client) if the device token is missing/invalid."""
    if not settings.require_device_auth:
        return True
    token = getattr(msg, "device_token", None)
    if await verify_device(app.state.providers.memory, msg.elder_id, token):
        return True
    logger.warning("auth failed for elder %s", msg.elder_id)
    await websocket.send_text(json.dumps({"type": "ack", "received": "auth_failed"}))
    return False


class DemoIncidentRequest(BaseModel):
    trigger_source: str = "fall"
    escalated: bool = True
    summary: Optional[str] = None
    last_transcript: Optional[str] = None
    audio_clip_b64: Optional[str] = None


class AudioTranscriptRequest(BaseModel):
    audio_clip_b64: str


class ElderConversationRequest(BaseModel):
    transcript: str


@app.post("/elders/{elder_id}/demo/transcribe")
async def demo_transcribe(elder_id: str, body: AudioTranscriptRequest) -> dict[str, object]:
    providers = await _require_elder(elder_id)
    transcript_task = asyncio.create_task(providers.voice.transcribe(body.audio_clip_b64))
    scene_task = asyncio.create_task(providers.audio_scene.classify(body.audio_clip_b64))
    transcript, scene = await asyncio.gather(transcript_task, scene_task)
    return {
        "transcript": transcript,
        "wants_attention": wants_attention(transcript),
        "audio_scene": scene.to_dict(),
    }


@app.post("/elders/{elder_id}/voice/conversation")
async def elder_voice_conversation(
    elder_id: str, body: ElderConversationRequest
) -> dict[str, object]:
    providers = await _require_elder(elder_id)
    return await handle_elder_conversation(
        providers=providers,
        elder_id=elder_id,
        transcript=body.transcript,
        auto_emergency_fallback=settings.auto_emergency_fallback,
        caretaker_ack_timeout_seconds=settings.caretaker_ack_timeout_seconds,
    )


@app.post("/elders/{elder_id}/demo/incident")
async def demo_incident(elder_id: str, body: DemoIncidentRequest) -> dict[str, object]:
    """Demo helper: log an incident event (e.g. a fall the elder device
    detected on-device) so it surfaces on the caretaker dashboard. This is NOT
    the real WS/FSM escalation path — it's a lightweight bridge for the
    on-device role-switching demo."""
    from datetime import datetime, timezone

    providers = await _require_elder(elder_id)
    transcript = body.last_transcript or ""
    if not transcript and body.audio_clip_b64:
        transcript = await providers.voice.transcribe(body.audio_clip_b64)
    event = {
        "kind": "incident",
        "ts": datetime.now(timezone.utc).isoformat(),
        "trigger_source": body.trigger_source,
        "final_state": "escalated" if body.escalated else "resolved",
        "escalated": body.escalated,
        "last_transcript": transcript,
        "summary": body.summary
        or (
            "Fall detected on device; caretaker alerted."
            if body.escalated
            else "Fall check-in resolved on device."
        ),
    }
    await providers.memory.log_event(elder_id, event)
    escalation = None
    if body.escalated:
        await providers.telephony.send_sms(
            f"Quietcare alert for {elder_id}: {event['summary']}"
        )
        escalation = await call_caretaker_with_emergency_fallback(
            providers=providers,
            elder_id=elder_id,
            summary=str(event["summary"]),
            severity="high",
            trigger_source=body.trigger_source,
            hard_fall=body.trigger_source == "fall",
            auto_emergency_fallback=settings.auto_emergency_fallback,
            caretaker_ack_timeout_seconds=settings.caretaker_ack_timeout_seconds,
        )
    return {"elder_id": elder_id, "event": event, "escalation": escalation}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    providers = app.state.providers
    registry: SessionRegistry = app.state.registry
    elder_id: str | None = None
    logger.info("ws connected")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                msg = parse_client_message(data)
            except Exception as exc:
                logger.warning("bad client frame: %s", exc)
                continue

            if isinstance(msg, (RegisterMessage, TriggerMessage, AudioProbeMessage, VoiceConversationMessage)):
                if not await _authorized(websocket, msg):
                    continue

            if isinstance(msg, RegisterMessage):
                elder_id = msg.elder_id
                session = registry.get(elder_id)
                if session is None:
                    session = ElderSession(websocket, elder_id, providers)
                    registry.set(elder_id, session)
                else:
                    session.ws = websocket
                session.reset_incident()
                logger.info("registered elder %s", elder_id)
                await session.send_status()

            elif isinstance(msg, TriggerMessage):
                elder_id = msg.elder_id
                session = registry.get(elder_id)
                if session is None:
                    session = ElderSession(websocket, elder_id, providers)
                    registry.set(elder_id, session)
                else:
                    session.ws = websocket
                _spawn(_safe_handle_trigger(session, msg))

            elif isinstance(msg, AudioResponseMessage):
                session = registry.get(msg.elder_id)
                if session:
                    session.on_audio_response(msg.prompt_id, msg.audio_clip_b64, msg.transcript)

            elif isinstance(msg, AudioProbeMessage):
                _spawn(_safe_handle_audio_probe(websocket, msg))

            elif isinstance(msg, VoiceConversationMessage):
                _spawn(_safe_handle_voice_conversation(websocket, msg))

            else:  # heartbeat
                logger.debug("heartbeat from %s", getattr(msg, "elder_id", "?"))

    except WebSocketDisconnect:
        logger.info("ws disconnected (elder=%s)", elder_id)
    except Exception as exc:
        capture(exc, where="ws_endpoint", elder_id=elder_id)
        logger.exception("ws error: %s", exc)


async def _safe_handle_trigger(session: ElderSession, trigger: TriggerMessage) -> None:
    try:
        await handle_trigger(session, trigger)
    except Exception as exc:
        capture(exc, where="handle_trigger", elder_id=session.elder_id)
        logger.exception("trigger handling failed: %s", exc)


async def _safe_handle_audio_probe(websocket: WebSocket, msg: AudioProbeMessage) -> None:
    try:
        providers = await _require_elder(msg.elder_id)
        transcript_task = asyncio.create_task(providers.voice.transcribe(msg.audio_clip_b64))
        scene_task = asyncio.create_task(providers.audio_scene.classify(msg.audio_clip_b64))
        transcript, scene = await asyncio.gather(transcript_task, scene_task)
        await websocket.send_text(
            AudioProbeResultMessage(
                elder_id=msg.elder_id,
                transcript=transcript,
                wants_attention=wants_attention(transcript),
                audio_scene=scene.to_dict(),
            ).model_dump_json()
        )
    except Exception as exc:
        capture(exc, where="audio_probe", elder_id=msg.elder_id)
        logger.exception("audio probe failed: %s", exc)


async def _safe_handle_voice_conversation(websocket: WebSocket, msg: VoiceConversationMessage) -> None:
    try:
        providers = await _require_elder(msg.elder_id)
        reply = await handle_elder_conversation(
            providers=providers,
            elder_id=msg.elder_id,
            transcript=msg.transcript,
            auto_emergency_fallback=settings.auto_emergency_fallback,
            caretaker_ack_timeout_seconds=settings.caretaker_ack_timeout_seconds,
        )
        await websocket.send_text(
            VoiceConversationReplyMessage(elder_id=msg.elder_id, **reply).model_dump_json()
        )
    except Exception as exc:
        capture(exc, where="voice_conversation", elder_id=msg.elder_id)
        logger.exception("voice conversation failed: %s", exc)
