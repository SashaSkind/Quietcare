"""Live check that Sentry (errors) and Arize AX (tracing) actually work.

  - Sentry: initialize and send a test event, returning its event id.
  - Arize: init_tracing(), emit an AGENT span with a nested TOOL span, then
    force-flush the OTel exporter so the spans are actually shipped to Arize.

Run:  python scripts/verify_observability.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app import observability as obs
from app.sentry_init import init_sentry


def check_sentry() -> None:
    print("=== Sentry (errors) ===")
    print(f"  has_sentry: {settings.has_sentry}")
    if not settings.has_sentry:
        print("  SENTRY_DSN unset -> no-op. Skipping.")
        return
    init_sentry()
    import sentry_sdk

    event_id = sentry_sdk.capture_message(
        "Quietcare observability verify: Sentry test event", level="info"
    )
    sentry_sdk.flush(timeout=10)
    print(f"  test event sent -> id={event_id}")


def check_arize() -> None:
    print("\n=== Arize AX (tracing) ===")
    print(f"  has_arize: {settings.has_arize} | project: {settings.arize_project_name}")
    if not settings.has_arize:
        print("  ARIZE_SPACE_ID/API_KEY unset -> no-op. Skipping.")
        return
    obs.init_tracing()
    if obs._tracer is None:
        print("  tracer did NOT initialize (check deps/keys).")
        return
    with obs.agent_span("verify", "synthetic verify run") as span:
        with obs.tool_span("get_elder_profile", {"elder_id": "margaret-01"}) as tspan:
            obs.record_output(tspan, '{"name": "Margaret", "age": 78}')
        obs.record_output(span, "resolved: verify trace")
    # Force-flush so spans actually ship before the process exits.
    from opentelemetry import trace

    provider = trace.get_tracer_provider()
    flushed = False
    if hasattr(provider, "force_flush"):
        flushed = provider.force_flush()  # type: ignore[attr-defined]
    time.sleep(1.0)
    print(f"  emitted AGENT+TOOL spans; force_flush -> {flushed}")
    print(f"  view in Arize UI under project '{settings.arize_project_name}'")


if __name__ == "__main__":
    check_sentry()
    check_arize()
