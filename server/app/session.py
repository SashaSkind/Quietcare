"""Per-elder session state + trigger orchestration + caretaker bus service."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .protocol import (
    AckMessage,
    ListenMessage,
    SpeakMessage,
    StatusMessage,
    TriggerMessage,
)
from .providers.factory import Providers
from .state_machine import EscalationStateMachine, State

logger = logging.getLogger("quietcare.session")

LISTEN_TIMEOUT_S = 15.0


class ElderSession:
    def __init__(self, websocket: Any, elder_id: str, providers: Providers) -> None:
        self.ws = websocket
        self.elder_id = elder_id
        self.providers = providers
        self.fsm = EscalationStateMachine(elder_id)

        self._prompt_n = 0
        self.current_prompt_id: Optional[str] = None
        self._pending: dict[str, asyncio.Future[Optional[str]]] = {}

        self.trigger_source = "manual"
        self.device_state: dict[str, Any] = {}
        self.hard_fall = False
        self.trigger_transcript = ""
        self.last_transcript = ""
        self.acoustic_evidence: dict[str, Any] = {}

    def reset_incident(self) -> None:
        """Start a fresh incident: a new FSM and cleared per-incident state.

        Sessions persist in the registry across reconnects, so each new
        registration/trigger must reset the escalation state.
        """
        self.fsm = EscalationStateMachine(self.elder_id)
        self._prompt_n = 0
        self.current_prompt_id = None
        self._pending.clear()
        self.last_transcript = ""
        self.trigger_transcript = ""
        self.acoustic_evidence = {}

    # ---- outbound ----
    async def _send(self, model: Any) -> None:
        await self.ws.send_text(model.model_dump_json())

    async def send_ack(self, received: str) -> None:
        await self._send(AckMessage(received=received))

    async def send_status(self) -> None:
        state = self.fsm.client_status
        logger.info("status[%s]=%s", self.elder_id, state)
        await self._send(StatusMessage(state=state))  # type: ignore[arg-type]

    def new_prompt_id(self) -> str:
        self._prompt_n += 1
        self.current_prompt_id = f"p{self._prompt_n}"
        return self.current_prompt_id

    async def send_speak(self, prompt_id: str, audio_b64: str, text: str) -> None:
        await self._send(
            SpeakMessage(prompt_id=prompt_id, audio_b64=audio_b64, text=text)
        )

    async def send_listen(self, prompt_id: str, duration_ms: int) -> None:
        await self._send(ListenMessage(prompt_id=prompt_id, duration_ms=duration_ms))

    # ---- check-in request/response correlation ----
    async def await_audio_response(self, prompt_id: str) -> Optional[str]:
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[Optional[str]] = loop.create_future()
        self._pending[prompt_id] = fut
        try:
            return await asyncio.wait_for(fut, timeout=LISTEN_TIMEOUT_S)
        except asyncio.TimeoutError:
            logger.info("listen timeout for %s/%s (no response)", self.elder_id, prompt_id)
            return None
        finally:
            self._pending.pop(prompt_id, None)

    def on_audio_response(self, prompt_id: str, audio_b64: Optional[str]) -> None:
        fut = self._pending.get(prompt_id)
        if fut and not fut.done():
            fut.set_result(audio_b64)

    # ---- FSM transitions (with status emission) ----
    async def begin_checkin_once(self) -> None:
        if self.fsm.state == State.TRIGGERED:
            self.fsm.begin_checkin()
            await self.send_status()

    async def escalate(self, *, hard_fall: bool = False) -> None:
        if self.fsm.state in (State.TRIGGERED, State.CHECKING_IN):
            self.fsm.escalate(hard_fall=hard_fall)
            await self.send_status()

    def caretaker_notified_once(self) -> None:
        if self.fsm.state == State.ESCALATING:
            self.fsm.caretaker_notified()

    async def resolve(self) -> None:
        if self.fsm.state == State.CHECKING_IN:
            self.fsm.resolve()
            await self.send_status()


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, ElderSession] = {}

    def set(self, elder_id: str, session: ElderSession) -> None:
        self._sessions[elder_id] = session

    def get(self, elder_id: str) -> Optional[ElderSession]:
        return self._sessions.get(elder_id)

    def remove(self, elder_id: str) -> None:
        self._sessions.pop(elder_id, None)


async def handle_trigger(session: ElderSession, trigger: TriggerMessage) -> None:
    """Run the full elder-agent flow for one trigger (as a background task)."""
    from .agents.elder import run_elder_agent  # local import avoids cycle

    p = session.providers
    session.reset_incident()
    session.trigger_source = trigger.trigger_source
    session.device_state = trigger.device_state.model_dump()
    # Heuristic: an unambiguous hard fall may bypass the check-in requirement.
    session.hard_fall = trigger.trigger_source == "fall"

    await session.send_ack("trigger")
    session.fsm.trigger()
    await session.send_status()

    # Acoustic context from the pre-event clip (decision uses the check-in).
    session.trigger_transcript = await p.voice.transcribe(trigger.audio_clip_b64)
    logger.info("trigger acoustic context: %r", session.trigger_transcript)

    # Non-speech distress detection (thud/scream/groan) on the trigger clip.
    scene = await p.audio_scene.classify(trigger.audio_clip_b64)
    session.acoustic_evidence["trigger"] = scene.to_dict()
    logger.info("trigger audio scene: %s", scene.to_dict())

    summary = await run_elder_agent(session, p.llm)
    logger.info("elder-agent done: %s", summary)

    # If the agent didn't escalate, resolve the check-in.
    await session.resolve()
    logger.info("FSM trace[%s]: %s", session.elder_id, session.fsm.trace())

    # Persist a structured incident record regardless of which tools the LLM
    # chose to call, so the caretaker history is always complete.
    escalated = session.fsm.state in (
        State.ESCALATING,
        State.CARETAKER_NOTIFIED,
        State.HUMAN_ACK,
        State.GATED_911,
    )
    incident = {
        "kind": "incident",
        "ts": datetime.now(timezone.utc).isoformat(),
        "trigger_source": session.trigger_source,
        "final_state": session.fsm.state.value,
        "fsm_trace": session.fsm.trace(),
        "escalated": escalated,
        "last_transcript": session.last_transcript,
        "summary": summary,
    }
    try:
        await p.memory.log_event(session.elder_id, incident)
    except Exception as exc:  # pragma: no cover - external store
        logger.warning("incident persist failed (%s)", exc)


class CaretakerService:
    """Subscribes to the bus and runs the caretaker-agent per escalation."""

    def __init__(
        self,
        providers: Providers,
        registry: SessionRegistry,
        confirmations: Any = None,
    ) -> None:
        self.providers = providers
        self.registry = registry
        self.confirmations = confirmations
        self.last_result: Optional[str] = None

    def attach(self) -> None:
        self.providers.bus.subscribe(self._handle)

    async def _handle(self, msg: dict[str, Any]) -> None:
        if msg.get("topic") != "caretaker.notify":
            return
        from .agents.caretaker import run_caretaker_agent

        elder_id = msg.get("elder_id", "")
        session = self.registry.get(elder_id)
        if session is None:
            logger.warning("caretaker: no session for %s", elder_id)
            return
        logger.info("caretaker-agent handling: %s", json.dumps(msg))
        self.last_result = await run_caretaker_agent(
            session, self.providers.llm, msg, self.confirmations
        )
        logger.info("caretaker-agent done: %s", self.last_result)


async def confirm_911(
    *,
    registry: SessionRegistry,
    confirmations: Any,
    providers: Providers,
    elder_id: str,
    token: str,
    approve: bool,
) -> dict[str, Any]:
    """Resolve a human 911 authorization. On approval, gate the FSM and dispatch
    the (configurable, mock-by-default) emergency call. Raises on bad token /
    missing request so the caller can return the right HTTP status."""
    pc = confirmations.resolve(elder_id, token, approve)  # KeyError/Perm/Value
    if not approve:
        logger.info("911 authorization REJECTED for %s", elder_id)
        return {"status": "rejected", "elder_id": elder_id}

    # ArmorIQ gate: even after human approval, the emergency dispatch must be
    # sanctioned by the policy gate before it can fire.
    decision = await providers.policy_gate.sanction(
        "emergency_dispatch",
        {"elder_id": elder_id, "reason": pc.reason, "summary": pc.summary},
    )
    if not decision.allowed:
        logger.warning(
            "emergency dispatch BLOCKED by policy gate for %s: %s",
            elder_id,
            decision.reason,
        )
        return {
            "status": "blocked_by_policy",
            "elder_id": elder_id,
            "reason": decision.reason,
        }

    session = registry.get(elder_id)
    if session is not None:
        session.fsm.gate_911(human_confirmed=True)
        await session.send_status()
    res = await providers.telephony.dispatch_emergency(pc.summary or pc.reason)
    logger.info("911 authorization CONFIRMED for %s; dispatch=%s", elder_id, res.detail)
    return {
        "status": "confirmed",
        "elder_id": elder_id,
        "dispatch": {"ok": res.ok, "mocked": res.mocked, "detail": res.detail},
    }
