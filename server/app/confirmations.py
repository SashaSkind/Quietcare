"""Human-in-the-loop confirmation registry for the gated 911 path.

The caretaker-agent never dials emergency services autonomously. Instead it
creates a *pending confirmation* and alerts a human, who must explicitly approve
via the HTTP endpoint. This module holds the (in-memory) pending requests and
their one-time tokens.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PendingConfirmation:
    elder_id: str
    reason: str
    summary: str
    token: str
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending | confirmed | rejected


class ConfirmationRegistry:
    """In-memory store of pending 911 confirmations keyed by elder_id."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingConfirmation] = {}

    def create(self, elder_id: str, reason: str, summary: str) -> PendingConfirmation:
        pc = PendingConfirmation(
            elder_id=elder_id,
            reason=reason,
            summary=summary,
            token=secrets.token_urlsafe(16),
        )
        self._pending[elder_id] = pc
        return pc

    def get(self, elder_id: str) -> Optional[PendingConfirmation]:
        return self._pending.get(elder_id)

    def resolve(self, elder_id: str, token: str, approve: bool) -> PendingConfirmation:
        """Validate the token and mark the confirmation confirmed/rejected.

        Raises KeyError if there's no pending request, and PermissionError if the
        token does not match (prevents spoofed authorizations).
        """
        pc = self._pending.get(elder_id)
        if pc is None:
            raise KeyError(f"no pending 911 confirmation for {elder_id}")
        if pc.status != "pending":
            raise ValueError(f"confirmation already {pc.status}")
        if not secrets.compare_digest(pc.token, token):
            raise PermissionError("invalid confirmation token")
        pc.status = "confirmed" if approve else "rejected"
        return pc
