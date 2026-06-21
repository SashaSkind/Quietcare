"""MessageBus provider: BAND with an in-process async fan-out mock (default).

The mock dispatches published messages directly to registered async handlers and
awaits them, which keeps the end-to-end demo deterministic (the caretaker-agent
finishes before the trigger handler returns).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

logger = logging.getLogger("quietcare.bus")

Handler = Callable[[dict[str, Any]], Awaitable[None]]


class MessageBus(ABC):
    name: str = "bus"

    @abstractmethod
    def subscribe(self, handler: Handler) -> None:
        ...

    @abstractmethod
    async def publish(self, msg: dict[str, Any]) -> None:
        ...


class InProcessBus(MessageBus):
    name = "in-process"

    def __init__(self) -> None:
        self._handlers: list[Handler] = []

    def subscribe(self, handler: Handler) -> None:
        self._handlers.append(handler)

    async def publish(self, msg: dict[str, Any]) -> None:
        logger.info("bus publish: %s", msg.get("topic", msg))
        for handler in list(self._handlers):
            await handler(msg)


class BandBus(MessageBus):
    """BAND-backed bus using the real Agent API (https://docs.band.ai).

    BAND is an agent mesh built around chat rooms: agents authenticate with an
    ``X-API-Key`` header against ``/api/v1/agent`` and exchange *messages*
    (directed, require @mentions) or *events* (informational, no mentions).

    This bus mirrors every escalation into a dedicated BAND chat room as an
    ``event`` — a real, replayable write you can see in the BAND dashboard —
    while still dispatching to the in-process handlers so the local caretaker
    flow stays deterministic. All network calls degrade gracefully: a BAND
    outage never blocks the in-app escalation.
    """

    name = "band"

    def __init__(self, api_key: str, base_url: str, room_title: str = "Quietcare") -> None:
        import asyncio

        import httpx  # lazy import

        # ``base_url`` may be the bare host (e.g. https://app.band.ai/); the
        # Agent API lives under /api/v1/agent.
        root = (base_url or "https://app.band.ai").rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=root,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=15.0,
            follow_redirects=True,
        )
        self._room_title = room_title
        self._handlers: list[Handler] = []
        self._chat_id: str | None = None
        self._lock = asyncio.Lock()

    def subscribe(self, handler: Handler) -> None:
        self._handlers.append(handler)

    async def _ensure_room(self) -> str | None:
        """Lazily resolve (or create) the Quietcare chat room id, cached."""
        if self._chat_id:
            return self._chat_id
        async with self._lock:
            if self._chat_id:
                return self._chat_id
            # Reuse an existing room with our title if present.
            r = await self._client.get("/api/v1/agent/chats")
            r.raise_for_status()
            for room in r.json().get("data", []):
                if room.get("title") == self._room_title:
                    self._chat_id = room["id"]
                    return self._chat_id
            # Otherwise create one.
            c = await self._client.post(
                "/api/v1/agent/chats", json={"chat": {"title": self._room_title}}
            )
            c.raise_for_status()
            self._chat_id = c.json()["data"]["id"]
            logger.info("BAND: created chat room %s (%s)", self._chat_id, self._room_title)
            return self._chat_id

    async def publish(self, msg: dict[str, Any]) -> None:
        # 1) Mirror to BAND as an event (best-effort, never blocks the flow).
        try:
            chat_id = await self._ensure_room()
            if chat_id:
                topic = msg.get("topic", "event")
                summary = msg.get("summary") or msg.get("reason") or topic
                await self._client.post(
                    f"/api/v1/agent/chats/{chat_id}/events",
                    json={
                        "event": {
                            "content": f"[{topic}] {summary}",
                            "message_type": "task",
                            "metadata": msg,
                        }
                    },
                )
        except Exception as exc:  # pragma: no cover - network
            logger.warning("BAND publish failed (%s); dispatching locally", exc)
        # 2) Always dispatch to local handlers (deterministic in-app flow).
        for handler in list(self._handlers):
            await handler(msg)
