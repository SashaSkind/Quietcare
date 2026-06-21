"""FastAPI app: GET /health and WS /ws implementing the protocol v1 server side."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from typing import Optional

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .auth import provision_device, verify_device
from .config import settings
from .confirmations import ConfirmationRegistry
from .protocol import (
    AudioResponseMessage,
    RegisterMessage,
    TriggerMessage,
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
    caretaker = CaretakerService(providers, registry, confirmations)
    caretaker.attach()

    app.state.providers = providers
    app.state.registry = registry
    app.state.confirmations = confirmations
    app.state.caretaker = caretaker
    app.state.bg_tasks = set()
    logger.info("Quietcare backend up. providers=%s", providers.summary())
    yield
    logger.info("Quietcare backend shutting down.")


app = FastAPI(title="Quietcare Backend", version="0.1.0", lifespan=lifespan)


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

            if isinstance(msg, (RegisterMessage, TriggerMessage)):
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
                    session.on_audio_response(msg.prompt_id, msg.audio_clip_b64)

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
