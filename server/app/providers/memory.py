"""Memory provider: Redis-backed store with an in-memory mock fallback.

Keys are namespaced as ``elder:{id}:*``. The mock seeds a sample elder profile
(Margaret) so the agents have realistic context with no external store.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

ELDERS_INDEX = "elders:index"

SAMPLE_ELDER = {
    "elder_id": "margaret-01",
    "name": "Margaret",
    "age": 78,
    "medications": ["blood-pressure medication"],
    "conditions": ["hypertension"],
    "prior_falls": 1,
    "notes": "Lives alone; one prior fall last year. Generally independent.",
    "caretaker": {"name": "Sarah (daughter)", "phone": "+1-555-0100"},
}


class Memory(ABC):
    name: str = "memory"

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        ...

    @abstractmethod
    async def set(self, key: str, value: Any) -> None:
        ...

    @abstractmethod
    async def list(self, key: str) -> list[Any]:
        ...

    @abstractmethod
    async def append(self, key: str, value: Any) -> None:
        ...

    # convenience helpers (namespaced)
    async def get_profile(self, elder_id: str) -> dict[str, Any] | None:
        return await self.get(f"elder:{elder_id}:profile")

    async def set_profile(self, elder_id: str, profile: dict[str, Any]) -> None:
        await self.set(f"elder:{elder_id}:profile", profile)
        await self._index_elder(elder_id)

    async def list_elders(self) -> list[str]:
        # The index may contain duplicates across appends; de-dup preserving order.
        seen: list[str] = []
        for eid in await self.list(ELDERS_INDEX):
            if eid not in seen:
                seen.append(eid)
        return seen

    async def _index_elder(self, elder_id: str) -> None:
        if elder_id not in await self.list_elders():
            await self.append(ELDERS_INDEX, elder_id)

    async def get_events(self, elder_id: str) -> list[Any]:
        return await self.list(f"elder:{elder_id}:events")

    async def log_event(self, elder_id: str, event: Any) -> None:
        await self.append(f"elder:{elder_id}:events", event)

    async def set_device_token(self, elder_id: str, token: str) -> None:
        await self.set(f"elder:{elder_id}:device_token", token)

    async def get_device_token(self, elder_id: str) -> str | None:
        return await self.get(f"elder:{elder_id}:device_token")


class RedisMemory(Memory):
    name = "redis"

    def __init__(self, url: str) -> None:
        import redis.asyncio as redis  # lazy import

        self._r = redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> Any | None:
        raw = await self._r.get(key)
        return json.loads(raw) if raw is not None else None

    async def set(self, key: str, value: Any) -> None:
        await self._r.set(key, json.dumps(value))

    async def list(self, key: str) -> list[Any]:
        items = await self._r.lrange(key, 0, -1)
        return [json.loads(i) for i in items]

    async def append(self, key: str, value: Any) -> None:
        await self._r.rpush(key, json.dumps(value))

    async def seed(self) -> None:
        existing = await self.get_profile(SAMPLE_ELDER["elder_id"])
        if existing is None:
            await self.set_profile(SAMPLE_ELDER["elder_id"], SAMPLE_ELDER)
        else:
            # Profile predates the elder index (older deployments); ensure it's
            # listed so multi-elder endpoints surface it.
            await self._index_elder(SAMPLE_ELDER["elder_id"])


class MockMemory(Memory):
    name = "mock"

    def __init__(self) -> None:
        self._kv: dict[str, Any] = {}
        self._lists: dict[str, list[Any]] = {}
        # seed the sample elder + index
        self._kv[f"elder:{SAMPLE_ELDER['elder_id']}:profile"] = SAMPLE_ELDER
        self._lists[ELDERS_INDEX] = [SAMPLE_ELDER["elder_id"]]

    async def get(self, key: str) -> Any | None:
        return self._kv.get(key)

    async def set(self, key: str, value: Any) -> None:
        self._kv[key] = value

    async def list(self, key: str) -> list[Any]:
        return list(self._lists.get(key, []))

    async def append(self, key: str, value: Any) -> None:
        self._lists.setdefault(key, []).append(value)
