"""Arize AX observability: OpenTelemetry tracing of the agent tool-use loop.

When ARIZE_SPACE_ID + ARIZE_API_KEY are set, ``init_tracing()`` registers an
OTel tracer provider pointed at Arize (via ``arize-otel``) and turns on
OpenInference auto-instrumentation for the Anthropic SDK, so every Claude call
(including via the PaleBlueDot gateway) is captured as an LLM span. The agent
loop adds AGENT/TOOL spans on top via the helpers below.

Everything degrades to a no-op when keys are absent or the optional deps aren't
installed, so the system runs unchanged with zero observability config.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from .config import settings

logger = logging.getLogger("quietcare.observability")

# OpenInference semantic-convention attribute keys (string literals so we don't
# hard-depend on the semconv package at call sites).
_SPAN_KIND = "openinference.span.kind"
_INPUT_VALUE = "input.value"
_OUTPUT_VALUE = "output.value"
_TOOL_NAME = "tool.name"

_initialized = False
_tracer: Optional[Any] = None  # opentelemetry Tracer when active, else None


def init_tracing() -> None:
    """Register the Arize tracer provider and instrument Anthropic. Idempotent;
    no-op when keys are missing or optional deps aren't installed."""
    global _initialized, _tracer
    if _initialized or not settings.has_arize:
        return
    try:
        from arize.otel import register

        tracer_provider = register(
            space_id=settings.arize_space_id,
            api_key=settings.arize_api_key,
            project_name=settings.arize_project_name,
        )
        # Auto-instrument the Anthropic SDK (captures Claude calls through the
        # PBD gateway too, since instrumentation patches the client methods).
        try:
            from openinference.instrumentation.anthropic import AnthropicInstrumentor

            AnthropicInstrumentor().instrument(tracer_provider=tracer_provider)
            logger.info("Arize: Anthropic auto-instrumentation enabled")
        except Exception as exc:  # pragma: no cover - optional dep
            logger.warning("Arize: Anthropic instrumentation unavailable (%s)", exc)

        _tracer = tracer_provider.get_tracer("quietcare")
        _initialized = True
        logger.info(
            "Arize tracing initialized (project=%s)", settings.arize_project_name
        )
    except Exception as exc:  # pragma: no cover - optional dep / network
        logger.warning("Arize tracing init failed: %s", exc)


def _set(span: Any, key: str, value: Any) -> None:
    try:
        span.set_attribute(key, value if isinstance(value, str) else str(value))
    except Exception:  # pragma: no cover - defensive
        pass


@contextmanager
def agent_span(label: str, user_prompt: str) -> Iterator[Any]:
    """Span covering one agent run (kind=AGENT). No-op when tracing is off."""
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(f"agent.{label}") as span:
        _set(span, _SPAN_KIND, "AGENT")
        _set(span, _INPUT_VALUE, user_prompt)
        yield span


@contextmanager
def tool_span(name: str, tool_input: Any) -> Iterator[Any]:
    """Span covering one tool dispatch (kind=TOOL). No-op when tracing is off."""
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(f"tool.{name}") as span:
        _set(span, _SPAN_KIND, "TOOL")
        _set(span, _TOOL_NAME, name)
        _set(span, _INPUT_VALUE, tool_input)
        yield span


def record_output(span: Any, output: Any) -> None:
    """Attach an output value to an active span (no-op if span is None)."""
    if span is None:
        return
    _set(span, _OUTPUT_VALUE, output)
