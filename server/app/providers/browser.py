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
        # Anti-bot helpers (off by default to keep the refill path lean; enable
        # per task via context for sites behind Cloudflare/Akamai, e.g. demos).
        payload: dict = {"projectId": self._project_id}
        browser_settings: dict = {}
        if context.get("solve_captchas"):
            browser_settings["solveCaptchas"] = True
        if context.get("advanced_stealth"):
            browser_settings["advancedStealth"] = True
        if browser_settings:
            payload["browserSettings"] = browser_settings
        if context.get("proxies"):
            payload["proxies"] = True
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    self.SESSIONS_URL,
                    headers={
                        "X-BB-API-Key": self._api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
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
            target_url = context.get("pharmacy_url") or context.get("url")
            if target_url and connect_url:
                nav_detail = await self._automate(connect_url, target_url, task, context)
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

    # Default visible-text controls to click, covering both the refill path and
    # the everyday add-to-cart path. Override per task via context["click_labels"].
    DEFAULT_CLICK_LABELS = (
        "Add to Cart",
        "Add to cart",
        "Add to Basket",
        "Add to bag",
        "Refill",
        "Request refill",
        "Reorder",
        "Renew",
    )

    async def _automate(
        self, connect_url: str, target_url: str, task: str, context: dict
    ) -> str:
        """Drive the live session via Playwright over CDP. Best-effort + defensive
        so a portal hiccup never raises into the caller.

        Supports an optional product search (``context["search"]``) and a
        configurable set of controls to click (``context["click_labels"]``),
        defaulting to refill + add-to-cart labels. Captures a screenshot to
        ``context["screenshot_path"]`` when provided (handy for demos)."""
        try:
            from playwright.async_api import async_playwright  # lazy, optional
        except Exception:
            return "playwright not installed; session-only (navigation skipped)"

        search = context.get("search")
        labels = tuple(context.get("click_labels") or self.DEFAULT_CLICK_LABELS)
        screenshot_path = context.get("screenshot_path")
        steps: list[str] = []

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(connect_url)
                ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
                title = await self._await_challenge(page)
                steps.append(f"navigated to '{title}'")

                # Optional: search for a product, then open the first result.
                if search:
                    if await self._search_product(page, search):
                        steps.append(f"searched '{search}'")
                    else:
                        steps.append(f"search box for '{search}' not found")

                # Click the first matching control (add-to-cart / refill).
                clicked_label = await self._click_first(page, labels)
                steps.append(
                    f"clicked '{clicked_label}'" if clicked_label
                    else "no add-to-cart/refill control found (manual review)"
                )

                if screenshot_path:
                    try:
                        await page.screenshot(path=screenshot_path, full_page=False)
                        steps.append(f"screenshot -> {screenshot_path}")
                    except Exception as exc:  # pragma: no cover - defensive
                        steps.append(f"screenshot failed ({exc})")

                await browser.close()
                return "; ".join(steps)
        except Exception as exc:
            logger.warning("Browserbase automation error (%s)", exc)
            steps.append(f"navigation error: {exc}")
            return "; ".join(steps)

    @staticmethod
    async def _await_challenge(page, timeout_s: float = 30.0) -> str:
        """Wait out a Cloudflare/Akamai interstitial (Browserbase solves it in
        the background) until the real page title appears. Returns the title."""
        import asyncio as _asyncio

        markers = ("just a moment", "performing security", "checking your browser",
                   "verify you are human", "attention required")
        deadline = _asyncio.get_event_loop().time() + timeout_s
        title = await page.title()
        while any(m in (title or "").lower() for m in markers):
            if _asyncio.get_event_loop().time() > deadline:
                break
            await _asyncio.sleep(2)
            try:
                title = await page.title()
            except Exception:
                break
        return title

    @staticmethod
    async def _search_product(page, term: str) -> bool:
        """Type a query into the first plausible search box and submit."""
        selectors = (
            "input[type='search']",
            "input[name='search']",
            "input[placeholder*='Search' i]",
            "input[aria-label*='Search' i]",
        )
        for sel in selectors:
            try:
                box = page.locator(sel).first
                if await box.count() > 0:
                    await box.fill(term, timeout=5000)
                    await box.press("Enter")
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                    # Open the first product link if the results expose one.
                    for link_sel in ("a.product-thumb__link", ".product-layout a", "a[href*='product']"):
                        try:
                            link = page.locator(link_sel).first
                            if await link.count() > 0:
                                await link.click(timeout=5000)
                                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                                break
                        except Exception:
                            continue
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    async def _click_first(page, labels) -> str | None:
        """Click the first visible control matching any of ``labels``; return it."""
        for label in labels:
            try:
                btn = page.get_by_role("button", name=label, exact=False).first
                if await btn.count() > 0:
                    await btn.click(timeout=5000)
                    return label
            except Exception:
                pass
            try:
                loc = page.get_by_text(label, exact=False).first
                if await loc.count() > 0:
                    await loc.click(timeout=5000)
                    return label
            except Exception:
                continue
        return None
