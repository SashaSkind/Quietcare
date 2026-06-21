"""Wellness trend summaries for the caretaker.

Aggregates the elder's logged events over a window into a structured trend
("this week: 3 check-ins, all normal, slightly less active than usual") plus a
warm natural-language summary. Turns silence into reassurance.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .medications import adherence_summary

logger = logging.getLogger("quietcare.wellness")

WELLNESS_SYSTEM = (
    "You are Quietcare's caretaker assistant writing a brief, warm weekly "
    "wellness update for a family caretaker. In 2-4 plain-language sentences, "
    "summarize how their loved one has been using ONLY the provided stats. Be "
    "reassuring and concrete; highlight anything notable (missed meds, "
    "incidents, reduced activity) gently. Never invent data."
)


def _parse_ts(event: dict[str, Any]) -> datetime | None:
    ts = event.get("ts")
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def compute_trends(events: list[dict[str, Any]], now: datetime, days: int = 7) -> dict[str, Any]:
    """Aggregate events within the last ``days`` into trend stats."""
    cutoff = now - timedelta(days=days)
    window = [
        e for e in events
        if isinstance(e, dict) and (_parse_ts(e) is None or _parse_ts(e) >= cutoff)
    ]
    incidents = [e for e in window if e.get("kind") == "incident"]
    escalated = [e for e in incidents if e.get("escalated")]
    checkins = [e for e in incidents if e.get("trigger_source") in ("scheduled", "manual", "inactivity", "fall", "audio_event")]
    by_source: dict[str, int] = {}
    for e in incidents:
        src = e.get("trigger_source", "unknown")
        by_source[src] = by_source.get(src, 0) + 1
    meds = adherence_summary(window)
    wandering = sum(1 for e in incidents if e.get("trigger_source") == "geofence")
    return {
        "days": days,
        "total_events": len(window),
        "incidents": len(incidents),
        "escalations": len(escalated),
        "check_ins": len(checkins),
        "by_trigger_source": by_source,
        "wandering_alerts": wandering,
        "medication": meds,
        "all_normal": len(escalated) == 0,
    }


def _deterministic_summary(name: str, t: dict[str, Any]) -> str:
    parts = [f"This week for {name}: {t['check_ins']} check-in(s)"]
    if t["escalations"] == 0:
        parts.append("all normal, no alerts")
    else:
        parts.append(f"{t['escalations']} escalation(s)")
    med = t["medication"]
    if med["total"]:
        rate = int((med["adherence_rate"] or 0) * 100)
        parts.append(f"medication adherence {rate}% ({med['missed']} missed)")
    if t["wandering_alerts"]:
        parts.append(f"{t['wandering_alerts']} wandering alert(s)")
    return ", ".join(parts) + "."


async def summarize_wellness(providers: Any, elder_id: str, days: int = 7) -> dict[str, Any]:
    memory = providers.memory
    profile = await memory.get_profile(elder_id) or {"elder_id": elder_id}
    events = await memory.get_events(elder_id)
    trends = compute_trends(events, datetime.now(timezone.utc), days)
    name = profile.get("name", elder_id)

    user = f"Stats for {name} (last {days} days): {json.dumps(trends)}"
    try:
        result = await providers.llm.run(
            WELLNESS_SYSTEM, [{"role": "user", "content": user}], []
        )
        summary = (result.text or "").strip()
    except Exception as exc:  # pragma: no cover - llm
        logger.warning("wellness LLM failed (%s)", exc)
        summary = ""
    if not summary:
        summary = _deterministic_summary(name, trends)
    return {"elder_id": elder_id, "days": days, "trends": trends, "summary": summary}
