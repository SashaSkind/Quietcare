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

    # Emergency dispatch (gated 911 path). NEVER set this to a real PSAP/911
    # line in a demo; use a safe test number you control. When unset, emergency
    # dispatch is logged only (mocked), even with real Twilio.
    emergency_number: str = ""

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
    def has_sentry(self) -> bool:
        return bool(self.sentry_dsn)


settings = Settings()
