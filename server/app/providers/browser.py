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

    Creates a cloud session, then — when a ``pharmacy_url`` is provided and
    Playwright is installed — connects over the session's CDP URL and drives the
    page (navigate, find a refill control by text, click it, capture the result).
    Without Playwright or a URL it gracefully returns the session id + replay URL.
    """

    name = "browserbase"

    SESSIONS_URL = "https://api.browserbase.com/v1/sessions"

    def __init__(self, api_key: str, project_id: str) -> None:
        self._api_key = api_key
        self._project_id = project_id

    async def run_task(self, task: str, context: Optional[dict] = None) -> BrowserTaskResult:
        import httpx

        context = context or {}
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
            connect_url = data.get("connectUrl") or data.get("connect_url")
            replay_url = (
                f"https://www.browserbase.com/sessions/{session_id}"
                if session_id else None
            )
            logger.info("Browserbase session %s created for task: %s", session_id, task)

            detail = f"Browserbase session created for task: {task}"
            pharmacy_url = context.get("pharmacy_url")
            if pharmacy_url and connect_url:
                nav_detail = await self._automate(connect_url, pharmacy_url, task)
                detail = f"{detail}; {nav_detail}"

            return BrowserTaskResult(
                ok=True,
                detail=detail,
                mocked=False,
                session_id=session_id,
                replay_url=replay_url,
            )
        except Exception as exc:  # pragma: no cover - network
            logger.warning("Browserbase task failed (%s)", exc)
            return BrowserTaskResult(ok=False, detail=f"error: {exc}", mocked=False)

    async def _automate(self, connect_url: str, pharmacy_url: str, task: str) -> str:
        """Drive the live session via Playwright over CDP. Best-effort + defensive
        so a portal hiccup never raises into the caller."""
        try:
            from playwright.async_api import async_playwright  # lazy, optional
        except Exception:
            return "playwright not installed; session-only (navigation skipped)"

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(connect_url)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(pharmacy_url, wait_until="domcontentloaded", timeout=30000)
                title = await page.title()
                # Heuristic: find a refill control by visible text.
                clicked = False
                for label in ("Refill", "Request refill", "Reorder", "Renew"):
                    try:
                        loc = page.get_by_text(label, exact=False).first
                        if await loc.count() > 0:
                            await loc.click(timeout=5000)
                            clicked = True
                            break
                    except Exception:
                        continue
                await browser.close()
                return (
                    f"navigated to '{title}', refill control "
                    + ("clicked" if clicked else "not found (manual review)")
                )
        except Exception as exc:
            logger.warning("Browserbase automation error (%s)", exc)
            return f"navigation error: {exc}"
