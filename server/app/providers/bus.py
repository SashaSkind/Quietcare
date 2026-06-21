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

    Two modes, selected by ``mention_handle``:

    - **Full @mention mesh** (``mention_handle`` set, e.g. "a.skinderev/elder"):
      on an ``escalation`` the app posts a real *message* into a room that
      @mentions the elder-agent daemon, which then recruits the caretaker daemon
      — autonomous agent-to-agent handoff. This is the "app nudges elder" hook.
    - **Event mirror** (no ``mention_handle``): escalations are written as silent
      *events* (visible in the BAND dashboard) but wake no agent.

    Either way the bus still dispatches to the in-process handlers so the local
    caretaker flow stays deterministic, and all network calls degrade gracefully:
    a BAND outage never blocks the in-app escalation.
    """

    name = "band"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        room_title: str = "Quietcare",
        mention_handle: str = "",
    ) -> None:
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
        self._mention_handle = mention_handle.strip()
        self._handlers: list[Handler] = []
        self._chat_id: str | None = None
        self._mention_id: str | None = None
        self._lock = asyncio.Lock()

    def subscribe(self, handler: Handler) -> None:
        self._handlers.append(handler)

    async def _resolve_mention_id(self) -> str | None:
        """Resolve the configured elder handle to a peer agent id (cached).

        Same-owner agents are auto-discoverable via /agent/peers, so no contact
        request is needed."""
        if not self._mention_handle:
            return None
        if self._mention_id:
            return self._mention_id
        r = await self._client.get("/api/v1/agent/peers", params={"page_size": 100})
        r.raise_for_status()
        for peer in r.json().get("data", []):
            if peer.get("handle") == self._mention_handle:
                self._mention_id = peer.get("id")
                return self._mention_id
        logger.warning("BAND: elder handle %s not found among peers", self._mention_handle)
        return None

    async def _ensure_room(self) -> str | None:
        """Lazily resolve (or create) the Quietcare chat room id, cached. When a
        mention handle is configured, also add that agent as a participant so it
        can be @mentioned."""
        if self._chat_id:
            return self._chat_id
        async with self._lock:
            if self._chat_id:
                return self._chat_id
            # Reuse an existing room with our title if present, else create one.
            r = await self._client.get("/api/v1/agent/chats")
            r.raise_for_status()
            chat_id = None
            for room in r.json().get("data", []):
                if room.get("title") == self._room_title:
                    chat_id = room["id"]
                    break
            if chat_id is None:
                c = await self._client.post(
                    "/api/v1/agent/chats", json={"chat": {"title": self._room_title}}
                )
                c.raise_for_status()
                chat_id = c.json()["data"]["id"]
                logger.info("BAND: created chat room %s (%s)", chat_id, self._room_title)
            # Add the elder agent as a participant (idempotent; ignore conflicts).
            mention_id = await self._resolve_mention_id()
            if mention_id:
                try:
                    await self._client.post(
                        f"/api/v1/agent/chats/{chat_id}/participants",
                        json={"participant": {"participant_id": mention_id, "role": "member"}},
                    )
                except Exception as exc:  # already a member, etc.
                    logger.debug("BAND: add elder participant (%s)", exc)
            self._chat_id = chat_id
            return self._chat_id

    async def publish(self, msg: dict[str, Any]) -> None:
        # 1) Push to BAND (best-effort, never blocks the flow).
        try:
            chat_id = await self._ensure_room()
            if chat_id:
                topic = msg.get("topic", "event")
                summary = msg.get("summary") or msg.get("reason") or topic
                mention_id = await self._resolve_mention_id()
                # The app's escalation tool publishes topic "caretaker.notify";
                # "escalation" is also accepted for direct callers.
                is_escalation = topic in ("caretaker.notify", "escalation")
                if mention_id and is_escalation:
                    # Full mesh: @mention the elder daemon to wake the handoff,
                    # handing it all the evidence so it can triage without asking
                    # the device (which cannot reply).
                    name = self._mention_handle.split("/")[-1]
                    parts = [f"Incident for {msg.get('elder_id', 'elder')}: {summary}"]
                    if msg.get("severity"):
                        parts.append(f"Severity: {msg['severity']}.")
                    if msg.get("evidence"):
                        parts.append(f"Evidence: {msg['evidence']}.")
                    parts.append("Assess and escalate to the caretaker if warranted.")
                    content = f"@{self._mention_handle} " + " ".join(parts)
                    await self._client.post(
                        f"/api/v1/agent/chats/{chat_id}/messages",
                        json={
                            "message": {
                                "content": content,
                                "mentions": [
                                    {
                                        "id": mention_id,
                                        "handle": self._mention_handle,
                                        "name": name,
                                        "kind": "mention",
                                    }
                                ],
                            }
                        },
                    )
                else:
                    # Event mirror: informational record, wakes no agent.
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
