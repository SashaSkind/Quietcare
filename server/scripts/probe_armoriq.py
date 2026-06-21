"""Throwaway probe to discover the ArmorIQ API shape. Safe: GET requests only."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx
from app.config import Settings

s = Settings()
base = s.armoriq_base_url.rstrip("/")
h = {"Authorization": f"Bearer {s.armoriq_api_key}"}
paths = ["/v1/scan", "/scan", "/v1/firewall", "/v1/inspect", "/v1/moderate",
         "/v1/prompt", "/v1/completions", "/chat/completions", "/v1/chat/completions",
         "/v1/analyze", "/analyze", "/v1/detect", "/detect", "/v1/audit",
         "/v1/authorize", "/authorize", "/v1/actions", "/actions", "/v1/agent"]
TARGET = "http://127.0.0.1:9?probe"  # harmless unreachable localhost target
bodies = [
    {"target": TARGET},
    {"targets": [TARGET]},
    {"url": TARGET},
    {"urls": [TARGET]},
    {"host": "127.0.0.1"},
    {"hosts": ["127.0.0.1"]},
    {"mcp_url": TARGET},
    {"mcp_endpoints": [TARGET]},
    {"endpoints": [TARGET]},
    {"server_url": TARGET},
]
with httpx.Client(timeout=20, headers=h, follow_redirects=True) as c:
    print("--- POST /scan with candidate bodies (looking for scanned_hosts>0 or validation errors) ---")
    for b in bodies:
        try:
            r = c.post(base + "/scan", json=b)
            try:
                j = r.json()
                meta = j.get("metadata", {}) if isinstance(j, dict) else {}
                sh = meta.get("scanned_hosts")
                rh = meta.get("reachable_hosts")
                print(f"{str(list(b.keys())):28} -> {r.status_code} scanned={sh} reachable={rh}")
            except Exception:
                print(f"{str(list(b.keys())):28} -> {r.status_code} {r.text[:120]}")
        except Exception as e:
            print(f"{str(list(b.keys())):28} -> ERR {e}")
