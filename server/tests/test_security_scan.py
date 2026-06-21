"""Tests for the ArmorIQ MCP security-scanner provider + admin endpoint.

The live ArmorIQ path is gated behind RUN_LIVE_TESTS; offline the mock is used.

Run with:  python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.confirmations import ConfirmationRegistry
from app.main import app
from app.providers.bus import InProcessBus
from app.providers.factory import Providers, _build_security_scan
from app.providers.llm import MockLLM
from app.providers.memory import MockMemory
from app.providers.security_scan import ArmorIQScanner, MockSecurityScanner
from app.providers.telephony import MockTelephony
from app.providers.voice import MockVoice
from app.session import CaretakerService, SessionRegistry


def _install_state(scanner=None) -> Providers:
    providers = Providers(
        llm=MockLLM(), voice=MockVoice(), memory=MockMemory(),
        telephony=MockTelephony(), bus=InProcessBus(),
        security_scan=scanner or MockSecurityScanner(),
    )
    registry = SessionRegistry()
    app.state.providers = providers
    app.state.registry = registry
    app.state.confirmations = ConfirmationRegistry()
    app.state.caretaker = CaretakerService(providers, registry)
    app.state.bg_tasks = set()
    return providers


class TestScannerProvider(unittest.IsolatedAsyncioTestCase):
    async def test_mock_returns_safe(self):
        res = await MockSecurityScanner().scan("http://example/mcp")
        self.assertTrue(res.ok and res.mocked)
        self.assertEqual(res.severity_level, "safe")

    async def test_armoriq_handles_unreachable(self):
        # Unreachable host -> ok=False, no exception.
        res = await ArmorIQScanner("k", "http://127.0.0.1:1").scan("http://x/mcp")
        self.assertFalse(res.ok)


class TestFactorySelection(unittest.TestCase):
    def test_mock_without_keys(self):
        self.assertEqual(_build_security_scan(Settings(_env_file=None)).name, "mock")

    def test_armoriq_with_keys(self):
        s = Settings(_env_file=None, armoriq_api_key="k", armoriq_base_url="https://x")
        self.assertEqual(_build_security_scan(s).name, "armoriq")

    def test_scan_target_list_parsing(self):
        s = Settings(_env_file=None, armoriq_scan_targets="http://a, http://b ,")
        self.assertEqual(s.scan_target_list, ["http://a", "http://b"])


class TestScanEndpoint(unittest.TestCase):
    def setUp(self):
        _install_state()
        self.client = TestClient(app)

    def tearDown(self):
        settings.admin_token = ""

    def test_scan_returns_report(self):
        resp = self.client.post("/admin/security-scan", json={"url": "http://x/mcp"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["url"], "http://x/mcp")
        self.assertIn("severity_level", body)

    def test_scan_guarded_by_admin_token(self):
        settings.admin_token = "secret"
        unauth = self.client.post("/admin/security-scan", json={"url": "http://x"})
        self.assertEqual(unauth.status_code, 401)
        ok = self.client.post(
            "/admin/security-scan", json={"url": "http://x"},
            headers={"X-Admin-Token": "secret"},
        )
        self.assertEqual(ok.status_code, 200)


@unittest.skipUnless(
    os.environ.get("RUN_LIVE_TESTS") == "1" and Settings().has_armoriq,
    "live ArmorIQ disabled (set RUN_LIVE_TESTS=1 + ARMORIQ_API_KEY/BASE_URL)",
)
class TestArmorIQLive(unittest.IsolatedAsyncioTestCase):
    async def test_scans_localhost(self):
        s = Settings()
        res = await ArmorIQScanner(s.armoriq_api_key, s.armoriq_base_url).scan(
            "http://127.0.0.1:9/mcp"
        )
        self.assertTrue(res.ok)
        self.assertIn(res.severity_level, ("safe", "low", "medium", "high", "critical"))


if __name__ == "__main__":
    unittest.main()
