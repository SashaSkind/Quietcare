"""Browser-automation provider for the everyday-care computer-use path.

Used for non-emergency errands like refilling a prescription on a pharmacy
portal. This ALWAYS runs off the emergency critical path (computer-use is slow
and flaky) so a booking hiccup can never block the safety loop.

Real implementation provisions a cloud browser session via Browserbase. When no
credentials are configured, a mock logs the intended task and returns a
structured result so the whole flow is testable with zero external calls.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger("quietcare.browser")


@dataclass
class BrowserTaskResult:
    ok: bool
    detail: str
    mocked: bool
    session_id: Optional[str] = None
    replay_url: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "detail": self.detail,
            "mocked": self.mocked,
            "session_id": self.session_id,
            "replay_url": self.replay_url,
        }


class Browser(ABC):
    name: str = "browser"

    @abstractmethod
    async def run_task(self, task: str, context: Optional[dict] = None) -> BrowserTaskResult:
        ...


class MockBrowser(Browser):
    name = "mock"

    async def run_task(self, task: str, context: Optional[dict] = None) -> BrowserTaskResult:
        logger.warning("WOULD RUN BROWSER TASK: %s (context=%s)", task, context)
        print(f"[BROWSER MOCK] WOULD RUN TASK: {task}")
        return BrowserTaskResult(
            ok=True, detail=f"mock browser task: {task}", mocked=True,
            session_id="mock-session", replay_url=None,
        )


class BrowserbaseBrowser(Browser):
    """Provisions a Browserbase cloud session for a task.

    A full computer-use run (driving a pharmacy portal via Playwright over the
    session's CDP URL) would attach here; this integration creates the session
    and returns its id + replay URL so the work is observable and resumable.
    """

    name = "browserbase"

    SESSIONS_URL = "https://api.browserbase.com/v1/sessions"

    def __init__(self, api_key: str, project_id: str) -> None:
        self._api_key = api_key
        self._project_id = project_id

    async def run_task(self, task: str, context: Optional[dict] = None) -> BrowserTaskResult:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    self.SESSIONS_URL,
                    headers={
                        "X-BB-API-Key": self._api_key,
                        "Content-Type": "application/json",
                    },
                    json={"projectId": self._project_id},
                )
            if resp.status_code not in (200, 201):
                return BrowserTaskResult(
                    ok=False, detail=f"Browserbase HTTP {resp.status_code}", mocked=False
                )
            data = resp.json()
            session_id = data.get("id")
            replay_url = (
                f"https://www.browserbase.com/sessions/{session_id}"
                if session_id else None
            )
            logger.info("Browserbase session %s created for task: %s", session_id, task)
            # NOTE: page automation (Playwright over data['connectUrl']) would run
            # here for a full refill flow; left as a follow-up so this stays robust.
            return BrowserTaskResult(
                ok=True,
                detail=f"Browserbase session created for task: {task}",
                mocked=False,
                session_id=session_id,
                replay_url=replay_url,
            )
        except Exception as exc:  # pragma: no cover - network
            logger.warning("Browserbase task failed (%s)", exc)
            return BrowserTaskResult(ok=False, detail=f"error: {exc}", mocked=False)
