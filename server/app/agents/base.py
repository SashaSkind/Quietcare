"""Provider-agnostic Claude tool-use loop shared by both agents."""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

from ..providers.llm import LLM
from ..sentry_init import capture

logger = logging.getLogger("quietcare.agent")

Dispatch = Callable[[str, dict[str, Any]], Awaitable[str]]


async def run_agent(
    *,
    llm: LLM,
    system: str,
    user_prompt: str,
    tools: list[dict[str, Any]],
    dispatch: Dispatch,
    label: str,
    max_iters: int = 10,
) -> str:
    """Drive a tool-use conversation until the model stops calling tools.

    Returns the model's final text. Tool failures are captured (Sentry) and fed
    back to the model as error strings rather than crashing the loop.
    """
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]

    for i in range(max_iters):
        try:
            result = await llm.run(system, messages, tools)
        except Exception as exc:
            capture(exc, agent=label, phase="llm")
            return f"[{label}] LLM error: {exc}"

        messages.append({"role": "assistant", "content": result.content})

        if result.stop_reason != "tool_use" or not result.tool_calls:
            logger.info("[%s] final: %s", label, result.text)
            return result.text

        tool_results: list[dict[str, Any]] = []
        for tc in result.tool_calls:
            logger.info("[%s] tool_call %s(%s)", label, tc.name, json.dumps(tc.input))
            try:
                output = await dispatch(tc.name, tc.input)
            except Exception as exc:
                capture(exc, agent=label, tool=tc.name)
                output = f"ERROR running {tc.name}: {exc}"
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": output,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    logger.warning("[%s] reached max_iters", label)
    return f"[{label}] stopped after {max_iters} iterations"
