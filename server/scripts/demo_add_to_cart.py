"""Live Browserbase add-to-cart demo runner.

Drives a real Browserbase session via Playwright to a storefront, optionally
searches for a product, clicks the first Add-to-Cart/Refill control, and saves a
screenshot. A hard asyncio timeout guarantees it always returns (no hangs), and
the Browserbase replay URL is printed so you can watch the recording.

Usage (from server/, with .venv active and ARIZE/BROWSERBASE keys in .env):

    python scripts/demo_add_to_cart.py \
        --url https://www.cvs.com/shop --search tylenol --anti-bot

    python scripts/demo_add_to_cart.py \
        --url https://www.scrapingcourse.com/ecommerce --search hoodie

Flags:
    --anti-bot   enable Browserbase proxies + CAPTCHA solving (for Cloudflare/
                 Akamai sites like CVS). Slower; needs a paid plan.
    --stealth    additionally request advancedStealth (Scale plan only).
    --timeout    overall seconds before giving up (default 120).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.providers.browser import BrowserbaseBrowser


async def _run(args) -> int:
    if not settings.has_browserbase:
        print("BROWSERBASE_API_KEY / PROJECT_ID not set; aborting.")
        return 2

    browser = BrowserbaseBrowser(
        settings.browserbase_api_key, settings.browserbase_project_id
    )
    ctx = {
        "url": args.url,
        "screenshot_path": args.screenshot,
    }
    if args.search:
        ctx["search"] = args.search
    if args.anti_bot:
        ctx["proxies"] = True
        ctx["solve_captchas"] = True
    if args.stealth:
        ctx["advanced_stealth"] = True

    try:
        res = await asyncio.wait_for(
            browser.run_task(f"Demo add-to-cart: {args.url}", ctx),
            timeout=args.timeout,
        )
    except asyncio.TimeoutError:
        print(f"TIMED OUT after {args.timeout}s (site likely blocked the session)")
        return 1

    d = res.to_dict()
    print("\n--- result ---")
    print("ok:        ", d["ok"])
    print("detail:    ", d["detail"])
    print("session:   ", d.get("session_id"))
    print("replay:    ", d.get("replay_url"))
    print("screenshot:", args.screenshot)
    added = "clicked" in d["detail"] and "cart" in d["detail"].lower()
    print("ADDED_TO_CART:", added)
    return 0 if added else 1


def main() -> None:
    p = argparse.ArgumentParser(description="Live Browserbase add-to-cart demo")
    p.add_argument("--url", required=True, help="storefront URL to open")
    p.add_argument("--search", default="", help="optional product search term")
    p.add_argument("--screenshot", default="/tmp/add_to_cart.png")
    p.add_argument("--anti-bot", action="store_true", help="proxies + CAPTCHA solving")
    p.add_argument("--stealth", action="store_true", help="advancedStealth (Scale plan)")
    p.add_argument("--timeout", type=float, default=120.0)
    args = p.parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
