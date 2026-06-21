"""FastAPI app: GET /health and WS /ws implementing the protocol v1 server side."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .config import settings
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
    caretaker = CaretakerService(providers, registry)
    caretaker.attach()

    app.state.providers = providers
    app.state.registry = registry
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


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    app.state.bg_tasks.add(task)
    task.add_done_callback(app.state.bg_tasks.discard)


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
