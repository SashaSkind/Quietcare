"""Centralized configuration sourced from environment variables / .env.

Every credential is optional. Helper properties report whether each real
provider has enough config to be used; otherwise the factory falls back to a
mock implementation so the system runs with no keys at all.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # LLM (direct Anthropic)
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-sonnet-4-6"

    # LLM (PaleBlueDot TokenRouter — Anthropic-compatible gateway serving Claude
    # with free credits). When the key is set, the LLM is routed through PBD; the
    # direct Anthropic key is used as a fallback. The base URL must be the PBD
    # endpoint the Anthropic SDK appends /v1/messages to.
    palebluedot_api_key: str = ""
    palebluedot_base_url: str = ""

    # Voice
    deepgram_api_key: str = ""

    # Audio-scene ML (AudioSet distress detection). Two backends are available:
    #   - YAMNet  (TFLite, light): set yamnet_model_path + yamnet_labels_path.
    #   - PANNs   (CNN14, heavy):  pip install panns-inference torch; the ~300MB
    #               checkpoint auto-downloads (or set panns_checkpoint_path).
    # audio_scene_backend selects which to use:
    #   auto    -> YAMNet if configured, else mock (PANNs never auto: it's heavy)
    #   yamnet  -> YAMNet (falls back to mock if unavailable)
    #   panns   -> PANNs  (falls back to mock if unavailable)
    #   both    -> ensemble of whichever are available (falls back to mock)
    #   mock    -> always the deterministic mock
    audio_scene_backend: str = "auto"
    yamnet_model_path: str = ""
    yamnet_labels_path: str = ""
    panns_checkpoint_path: str = ""

    # Memory
    redis_url: str = ""

    # Telephony
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    twilio_caretaker_number: str = ""

    # Message bus (BAND). REST URL is used for publish; WS URL is for streaming
    # subscriptions; base_url (an app/project id) is kept for future use.
    band_api_key: str = ""
    band_base_url: str = ""
    band_rest_url: str = ""
    band_ws_url: str = ""
    # Full @mention mesh: when set, the app (acting as its own BAND identity)
    # posts each escalation into a room @mentioning this elder-agent handle (e.g.
    # "a.skinderev/elder"), which then recruits the caretaker daemon. When empty,
    # BandBus falls back to posting a silent event (no agent is woken).
    band_elder_handle: str = ""

    # Emergency dispatch (gated 911 path). NEVER set this to a real PSAP/911
    # line in a demo; use a safe test number you control. When unset, emergency
    # dispatch is logged only (mocked), even with real Twilio.
    emergency_number: str = ""

    # Browser automation (Browserbase) for the everyday-care computer-use path
    # (e.g. medication refill on a pharmacy portal). When unset, a mock browser
    # logs the intended task. This always runs OFF the emergency critical path.
    browserbase_api_key: str = ""
    browserbase_project_id: str = ""

    # ArmorIQ MCP security scanner: scans MCP server endpoints for vulnerabilities
    # (SAFE-MCP techniques) and returns a vulnerability_score + severity_level via
    # POST {base_url}/scan {"url": ...}. armoriq_scan_targets is a comma-separated
    # list of MCP endpoint URLs to scan at startup (best-effort, logged).
    armoriq_api_key: str = ""
    armoriq_base_url: str = ""
    armoriq_scan_targets: str = ""

    # Local policy gate: in-code chokepoint that can physically block high-stakes
    # escalation actions ('escalation', 'emergency_dispatch'). Default allows;
    # policy_block_actions is a comma-separated kill-switch (e.g. "emergency_dispatch").
    # The gate also computes a deterministic risk score (0-100); emergency_dispatch
    # below emergency_min_risk is blocked unless human_confirmed is in context.
    policy_block_actions: str = ""
    emergency_min_risk: int = 0

    # Medication reminders: the scheduler tick interval (seconds) and how long to
    # wait for a spoken confirmation before logging a missed dose.
    med_tick_seconds: int = 60
    med_confirm_window_ms: int = 8000

    # Geofence / wandering: night-hours window (local 24h) during which leaving
    # the safe zone is treated as higher severity.
    night_start_hour: int = 22
    night_end_hour: int = 6

    # Arize AX observability: OpenTelemetry traces of the LLM tool-use loop are
    # exported to Arize via arize-otel + OpenInference auto-instrumentation. When
    # space_id + api_key are set, tracing is enabled; otherwise it's a no-op.
    # arize_project_name groups traces in the Arize UI.
    arize_space_id: str = ""
    arize_api_key: str = ""
    arize_project_name: str = "quietcare"

    # Sentry
    sentry_dsn: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # Auth: when true, WS register/trigger must carry a valid per-device token
    # (provision via POST /elders). Default false to keep the zero-config demo.
    require_device_auth: bool = False
    # Optional shared admin token guarding elder provisioning endpoints. When
    # unset, provisioning is open (suitable for local/demo only).
    admin_token: str = ""

    # ---- capability flags ----
    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_palebluedot(self) -> bool:
        return bool(self.palebluedot_api_key and self.palebluedot_base_url)

    @property
    def has_deepgram(self) -> bool:
        return bool(self.deepgram_api_key)

    @property
    def has_yamnet(self) -> bool:
        import os

        return bool(
            self.yamnet_model_path
            and self.yamnet_labels_path
            and os.path.exists(self.yamnet_model_path)
            and os.path.exists(self.yamnet_labels_path)
        )

    @property
    def has_redis(self) -> bool:
        return bool(self.redis_url)

    @property
    def has_twilio(self) -> bool:
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_from_number
            and self.twilio_caretaker_number
        )

    @property
    def has_band(self) -> bool:
        return bool(self.band_api_key and self.band_rest_url)

    @property
    def has_browserbase(self) -> bool:
        return bool(self.browserbase_api_key and self.browserbase_project_id)

    @property
    def has_armoriq(self) -> bool:
        return bool(self.armoriq_api_key and self.armoriq_base_url)

    @property
    def scan_target_list(self) -> list[str]:
        return [t.strip() for t in self.armoriq_scan_targets.split(",") if t.strip()]

    @property
    def blocked_action_set(self) -> set[str]:
        return {a.strip() for a in self.policy_block_actions.split(",") if a.strip()}

    @property
    def has_sentry(self) -> bool:
        return bool(self.sentry_dsn)

    @property
    def has_arize(self) -> bool:
        return bool(self.arize_space_id and self.arize_api_key)


settings = Settings()
