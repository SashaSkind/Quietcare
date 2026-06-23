"""Tests for multi-elder support, device provisioning, and per-device auth.

Run with:  python -m unittest discover -s tests
"""

import base64
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app import main as main_module
from app.auth import provision_device, verify_device
from app.config import settings
from app.confirmations import ConfirmationRegistry
from app.main import app
from app.providers.bus import InProcessBus
from app.providers.factory import Providers
from app.providers.llm import MockLLM
from app.providers.memory import MockMemory
from app.providers.telephony import MockTelephony
from app.providers.voice import MockVoice
from app.session import CaretakerService, SessionRegistry


def _mock_providers() -> Providers:
    return Providers(
        llm=MockLLM(),
        voice=MockVoice(),
        memory=MockMemory(),
        telephony=MockTelephony(),
        bus=InProcessBus(),
    )


def _install_state() -> Providers:
    """Install fresh mock app.state without running the real lifespan."""
    providers = _mock_providers()
    registry = SessionRegistry()
    confirmations = ConfirmationRegistry()
    app.state.providers = providers
    app.state.registry = registry
    app.state.confirmations = confirmations
    app.state.caretaker = CaretakerService(providers, registry, confirmations)
    app.state.bg_tasks = set()
    return providers


class TestMemoryMultiElder(unittest.IsolatedAsyncioTestCase):
    async def test_profiles_and_index(self):
        m = MockMemory()
        # Seeded elder is indexed.
        self.assertIn("margaret-01", await m.list_elders())
        await m.set_profile("frank-02", {"elder_id": "frank-02", "name": "Frank"})
        elders = await m.list_elders()
        self.assertIn("frank-02", elders)
        # No duplicate on re-set.
        await m.set_profile("frank-02", {"elder_id": "frank-02", "name": "Frank R."})
        self.assertEqual(elders.count("frank-02"), 1)

    async def test_event_isolation_between_elders(self):
        m = MockMemory()
        await m.log_event("a", {"k": 1})
        await m.log_event("b", {"k": 2})
        self.assertEqual([e["k"] for e in await m.get_events("a")], [1])
        self.assertEqual([e["k"] for e in await m.get_events("b")], [2])


class TestAuthHelpers(unittest.IsolatedAsyncioTestCase):
    async def test_provision_and_verify(self):
        m = MockMemory()
        token = await provision_device(m, "margaret-01")
        self.assertTrue(await verify_device(m, "margaret-01", token))

    async def test_reject_bad_and_missing(self):
        m = MockMemory()
        await provision_device(m, "margaret-01")
        self.assertFalse(await verify_device(m, "margaret-01", "wrong"))
        self.assertFalse(await verify_device(m, "margaret-01", None))
        # No token provisioned for this elder.
        self.assertFalse(await verify_device(m, "ghost", "anything"))


class TestElderEndpoints(unittest.TestCase):
    def setUp(self):
        _install_state()
        self.client = TestClient(app)

    def test_create_list_get(self):
        resp = self.client.post(
            "/elders",
            json={"elder_id": "frank-02", "name": "Frank", "age": 80},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["elder_id"], "frank-02")
        self.assertTrue(body["device_token"])  # token returned once

        elders = self.client.get("/elders").json()["elders"]
        self.assertIn("frank-02", elders)
        self.assertIn("margaret-01", elders)

        prof = self.client.get("/elders/frank-02").json()["profile"]
        self.assertEqual(prof["name"], "Frank")
        # Read API must not leak the device token.
        self.assertNotIn("device_token", self.client.get("/elders/frank-02").json())

    def test_duplicate_create_conflicts(self):
        self.client.post("/elders", json={"elder_id": "dup-1", "name": "X"})
        resp = self.client.post("/elders", json={"elder_id": "dup-1", "name": "X"})
        self.assertEqual(resp.status_code, 409)

    def test_get_unknown_404(self):
        self.assertEqual(self.client.get("/elders/nope").status_code, 404)

    def test_demo_transcribe_includes_audio_scene(self):
        payload = base64.b64encode(b"QC-SCENARIO-TRANSCRIPT:Hey Quietcare hello").decode("ascii")
        resp = self.client.post(
            "/elders/margaret-01/demo/transcribe",
            json={"audio_clip_b64": payload},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["transcript"], "Hey Quietcare hello")
        self.assertTrue(body["wants_attention"])
        self.assertEqual(body["audio_scene"]["source"], "mock")
        self.assertIn("tags", body["audio_scene"])

    def test_admin_token_guard(self):
        settings.admin_token = "secret"
        try:
            unauth = self.client.post("/elders", json={"elder_id": "z", "name": "Z"})
            self.assertEqual(unauth.status_code, 401)
            ok = self.client.post(
                "/elders",
                json={"elder_id": "z", "name": "Z"},
                headers={"X-Admin-Token": "secret"},
            )
            self.assertEqual(ok.status_code, 200)
        finally:
            settings.admin_token = ""


class TestWebSocketAuth(unittest.TestCase):
    def setUp(self):
        self.providers = _install_state()
        self.client = TestClient(app)
        settings.require_device_auth = True

    def tearDown(self):
        settings.require_device_auth = False

    def _provision(self, elder_id: str) -> str:
        import asyncio

        return asyncio.run(provision_device(self.providers.memory, elder_id))

    def test_register_rejected_without_token(self):
        with self.client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "register", "elder_id": "margaret-01"})
            msg = ws.receive_json()
            self.assertEqual(msg.get("received"), "auth_failed")

    def test_register_accepted_with_token(self):
        token = self._provision("margaret-01")
        with self.client.websocket_connect("/ws") as ws:
            ws.send_json(
                {"type": "register", "elder_id": "margaret-01", "device_token": token}
            )
            msg = ws.receive_json()
            # A valid register yields a status frame, not an auth_failed ack.
            self.assertEqual(msg.get("type"), "status")


if __name__ == "__main__":
    unittest.main()
