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
    """BAND-backed bus. Falls back to in-process semantics for subscription;
    publish posts to the BAND endpoint. Kept minimal and behind the same
    interface so it can be expanded without touching agents."""

    name = "band"

    def __init__(self, api_key: str, base_url: str) -> None:
        import httpx  # lazy import

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        self._handlers: list[Handler] = []

    def subscribe(self, handler: Handler) -> None:
        self._handlers.append(handler)

    async def publish(self, msg: dict[str, Any]) -> None:
        try:
            await self._client.post("/publish", json=msg)
        except Exception as exc:  # pragma: no cover - network
            logger.warning("BAND publish failed (%s); dispatching locally", exc)
        for handler in list(self._handlers):
            await handler(msg)
