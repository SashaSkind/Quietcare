"""SecurityScanner provider: ArmorIQ MCP vulnerability scanning.

ArmorIQ scans an MCP server endpoint for vulnerabilities (the SAFE-MCP technique
set) and returns a vulnerability_score + severity_level. This is a security
*posture* check (not an inline action gate) — used to vet the MCP endpoints the
system talks to. When no credentials are configured, a mock returns a "safe"
report so the system runs unchanged.

API contract (discovered):  POST {base_url}/scan  {"url": "<mcp endpoint>"}
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("quietcare.security_scan")


@dataclass
class ScanResult:
    ok: bool
    url: str
    severity_level: str = "unknown"
    vulnerability_score: float = 0.0
    scanned_hosts: int = 0
    reachable_hosts: int = 0
    mcp_endpoints: int = 0
    chain_attacks_detected: int = 0
    vulnerabilities: list = field(default_factory=list)
    mocked: bool = False
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "url": self.url,
            "severity_level": self.severity_level,
            "vulnerability_score": self.vulnerability_score,
            "scanned_hosts": self.scanned_hosts,
            "reachable_hosts": self.reachable_hosts,
            "mcp_endpoints": self.mcp_endpoints,
            "chain_attacks_detected": self.chain_attacks_detected,
            "vulnerabilities": self.vulnerabilities,
            "mocked": self.mocked,
            "detail": self.detail,
        }


class SecurityScanner(ABC):
    name: str = "security_scan"

    @abstractmethod
    async def scan(self, url: str) -> ScanResult:
        ...


class MockSecurityScanner(SecurityScanner):
    name = "mock"

    async def scan(self, url: str) -> ScanResult:
        logger.info("security scan (mock) for %s", url)
        return ScanResult(ok=True, url=url, severity_level="safe", mocked=True,
                          detail="mock scan (no ArmorIQ credentials)")


class ArmorIQScanner(SecurityScanner):
    name = "armoriq"

    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def scan(self, url: str) -> ScanResult:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._base_url}/scan",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"url": url},
                )
            if resp.status_code not in (200, 201):
                return ScanResult(
                    ok=False, url=url,
                    detail=f"ArmorIQ HTTP {resp.status_code}: {resp.text[:160]}",
                )
            data = resp.json()
            meta = data.get("metadata", {}) if isinstance(data, dict) else {}
            result = ScanResult(
                ok=True,
                url=url,
                severity_level=data.get("severity_level", "unknown"),
                vulnerability_score=float(data.get("vulnerability_score", 0) or 0),
                scanned_hosts=int(meta.get("scanned_hosts", 0) or 0),
                reachable_hosts=int(meta.get("reachable_hosts", 0) or 0),
                mcp_endpoints=int(meta.get("mcp_endpoints", 0) or 0),
                chain_attacks_detected=int(data.get("chain_attacks_detected", 0) or 0),
                vulnerabilities=data.get("vulnerabilities", []) or [],
                detail=f"severity={data.get('severity_level')} score={data.get('vulnerability_score')}",
            )
            logger.info("ArmorIQ scan %s -> %s", url, result.detail)
            return result
        except Exception as exc:  # pragma: no cover - network
            logger.warning("ArmorIQ scan failed for %s (%s)", url, exc)
            return ScanResult(ok=False, url=url, detail=f"error: {exc}")
