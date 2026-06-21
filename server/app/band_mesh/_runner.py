"""Shared runner for Quietcare's BAND @mention mesh.

Each Quietcare mesh agent is a long-running process that connects to BAND over a
persistent WebSocket (Phoenix channels) via the official ``band-sdk``. The SDK
injects the platform coordination tools (``band_lookup_peers``,
``band_add_participant``, ``band_send_message`` with @mentions, ``band_send_event``
…) so the LLM itself discovers peers and hands work off — no orchestration code.

The agents' Claude calls are routed through the **PaleBlueDot / TokenRouter**
Anthropic-compatible gateway (same as the rest of Quietcare), so no direct
Anthropic key is required. We point the SDK's ``AnthropicAdapter`` at the gateway
by setting ``ANTHROPIC_BASE_URL`` and handing it the gateway key.

Run an agent (from server/, with agent_config.yaml present):

    python -m app.band_mesh.elder
    python -m app.band_mesh.caretaker
"""

from __future__ import annotations

import asyncio
import logging
import os

from app.config import settings

logger = logging.getLogger("quietcare.band_mesh")


def _route_anthropic_through_palebluedot() -> str | None:
    """Point the Anthropic SDK (used by the SDK adapter) at the PaleBlueDot
    gateway via env. Returns the gateway key to hand the adapter, or None to use
    a direct Anthropic key from the environment."""
    if settings.has_palebluedot:
        base = settings.palebluedot_base_url.rstrip("/")
        # The Anthropic SDK appends /v1/messages; strip a trailing /v1 so the
        # gateway URL doesn't become /v1/v1/messages.
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        os.environ["ANTHROPIC_BASE_URL"] = base
        logger.info("BAND mesh: routing Claude via PaleBlueDot (%s)", base)
        return settings.palebluedot_api_key
    return settings.anthropic_api_key or None


async def run_agent(agent_key: str, instructions: str) -> None:
    """Boot a single mesh agent identified by ``agent_key`` in agent_config.yaml.

    ``instructions`` is the role prompt appended under the SDK's built-in
    coordination rules (peer discovery + @mention handoff)."""
    # Lazy imports so the rest of Quietcare runs without band-sdk installed.
    from band import Agent, run_with_graceful_shutdown
    from band.adapters import AnthropicAdapter
    from band.config import load_agent_config

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s"
    )

    agent_id, api_key = load_agent_config(agent_key)
    gateway_key = _route_anthropic_through_palebluedot()

    adapter = AnthropicAdapter(
        model=settings.anthropic_model,
        anthropic_api_key=gateway_key,
        prompt=instructions,
        enable_execution_reporting=True,  # surface tool calls/thoughts as room events
    )
    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=settings.band_ws_url or "wss://app.band.ai/api/v1/socket/websocket",
        rest_url=(settings.band_rest_url or "https://app.band.ai").rstrip("/"),
    )

    logger.info("Quietcare mesh agent '%s' is live. Ctrl+C to stop.", agent_key)
    await run_with_graceful_shutdown(agent)


def main(agent_key: str, instructions: str) -> None:
    asyncio.run(run_agent(agent_key, instructions))
