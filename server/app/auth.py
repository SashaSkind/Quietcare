"""Per-device identity + authentication for elder devices.

Each elder is provisioned a long random device token stored in memory under
``elder:{id}:device_token``. When ``settings.require_device_auth`` is enabled,
the WebSocket handler verifies this token on register/trigger so a device can
only act for the elder it was provisioned for.
"""

from __future__ import annotations

import secrets
from typing import Optional

from .providers.memory import Memory


async def provision_device(memory: Memory, elder_id: str) -> str:
    """Generate, store, and return a fresh device token for an elder."""
    token = secrets.token_urlsafe(24)
    await memory.set_device_token(elder_id, token)
    return token


async def verify_device(memory: Memory, elder_id: str, token: Optional[str]) -> bool:
    """Constant-time check that ``token`` matches the elder's stored token."""
    if not token:
        return False
    stored = await memory.get_device_token(elder_id)
    if not stored:
        return False
    return secrets.compare_digest(stored, token)
