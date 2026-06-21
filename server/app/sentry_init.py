"""Optional Sentry initialization. No-op when SENTRY_DSN is absent."""

from __future__ import annotations

import logging

from .config import settings

logger = logging.getLogger("quietcare.sentry")

_initialized = False


def init_sentry() -> None:
    global _initialized
    if _initialized or not settings.has_sentry:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[FastApiIntegration()],
            traces_sample_rate=0.1,
        )
        _initialized = True
        logger.info("Sentry initialized")
    except Exception as exc:  # pragma: no cover
        logger.warning("Sentry init failed: %s", exc)


def capture(exc: BaseException, **context) -> None:
    """Capture an exception if Sentry is active; always log it."""
    logger.exception("captured exception: %s", exc)
    if not settings.has_sentry:
        return
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for k, v in context.items():
                scope.set_extra(k, v)
            sentry_sdk.capture_exception(exc)
    except Exception:  # pragma: no cover
        pass
