"""Builds the provider set, auto-selecting real vs mock per available config."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..config import Settings
from .audio_scene import AudioScene, MockAudioScene, YamnetAudioScene
from .bus import BandBus, InProcessBus, MessageBus
from .llm import LLM, AnthropicLLM, MockLLM
from .memory import Memory, MockMemory, RedisMemory
from .telephony import MockTelephony, Telephony, TwilioTelephony
from .voice import DeepgramVoice, MockVoice, Voice

logger = logging.getLogger("quietcare.providers")


@dataclass
class Providers:
    llm: LLM
    voice: Voice
    memory: Memory
    telephony: Telephony
    bus: MessageBus
    # Defaulted so existing constructions (and tests) remain valid; the factory
    # always supplies a concrete instance.
    audio_scene: AudioScene = field(default_factory=MockAudioScene)

    def summary(self) -> dict[str, str]:
        return {
            "llm": self.llm.name,
            "voice": self.voice.name,
            "memory": self.memory.name,
            "telephony": self.telephony.name,
            "bus": self.bus.name,
            "audio_scene": self.audio_scene.name,
        }


def _build_llm(s: Settings) -> LLM:
    # Prefer PaleBlueDot TokenRouter (Anthropic-compatible gateway serving
    # Claude). The same Anthropic SDK client is pointed at PBD's base URL, so
    # tool-use / function-calling passes through unchanged.
    if s.has_palebluedot:
        try:
            llm = AnthropicLLM(
                s.palebluedot_api_key, s.palebluedot_base_url, s.anthropic_model
            )
            llm.name = "palebluedot"
            logger.info("LLM: routing Claude via PaleBlueDot TokenRouter")
            return llm
        except Exception as exc:  # missing sdk or bad config
            logger.warning(
                "PaleBlueDot init failed (%s); falling back to direct Anthropic", exc
            )
    if s.has_anthropic:
        try:
            return AnthropicLLM(s.anthropic_api_key, s.anthropic_base_url, s.anthropic_model)
        except Exception as exc:  # missing sdk or bad config
            logger.warning("Anthropic init failed (%s); using mock LLM", exc)
    return MockLLM()


def _build_voice(s: Settings) -> Voice:
    if s.has_deepgram:
        try:
            return DeepgramVoice(s.deepgram_api_key)
        except Exception as exc:
            logger.warning("Deepgram init failed (%s); using mock voice", exc)
    return MockVoice()


def _build_memory(s: Settings) -> Memory:
    if s.has_redis:
        try:
            return RedisMemory(s.redis_url)
        except Exception as exc:
            logger.warning("Redis init failed (%s); using mock memory", exc)
    return MockMemory()


def _build_telephony(s: Settings) -> Telephony:
    if s.has_twilio:
        try:
            return TwilioTelephony(
                s.twilio_account_sid,
                s.twilio_auth_token,
                s.twilio_from_number,
                s.twilio_caretaker_number,
                s.emergency_number,
            )
        except Exception as exc:
            logger.warning("Twilio init failed (%s); using mock telephony", exc)
    return MockTelephony()


def _build_bus(s: Settings) -> MessageBus:
    if s.has_band:
        try:
            return BandBus(s.band_api_key, s.band_rest_url)
        except Exception as exc:
            logger.warning("BAND init failed (%s); using in-process bus", exc)
    return InProcessBus()


def _build_audio_scene(s: Settings) -> AudioScene:
    if s.has_yamnet:
        try:
            scene = YamnetAudioScene(s.yamnet_model_path, s.yamnet_labels_path)
            logger.info("audio_scene: YAMNet model loaded")
            return scene
        except Exception as exc:
            logger.warning("YAMNet init failed (%s); using mock audio scene", exc)
    return MockAudioScene()


def build_providers(s: Settings) -> Providers:
    providers = Providers(
        llm=_build_llm(s),
        voice=_build_voice(s),
        memory=_build_memory(s),
        telephony=_build_telephony(s),
        bus=_build_bus(s),
        audio_scene=_build_audio_scene(s),
    )
    logger.info("providers: %s", providers.summary())
    return providers
