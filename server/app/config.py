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

    # Memory
    redis_url: str = ""

    # Telephony
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    twilio_caretaker_number: str = ""

    # Message bus
    band_api_key: str = ""
    band_base_url: str = ""

    # Sentry
    sentry_dsn: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

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
        return bool(self.band_api_key and self.band_base_url)

    @property
    def has_sentry(self) -> bool:
        return bool(self.sentry_dsn)


settings = Settings()
