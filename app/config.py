"""Configuration system for TTS service.

Loads config.yaml with environment variable substitution, then maps to typed
Pydantic models. All sensitive values (API keys) come from env vars.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Backend configs
# ---------------------------------------------------------------------------


class ElevenLabsConfig(BaseModel):
    enabled: bool = True
    api_key: str = ""
    default_voice_id: str = "XB0fDUnXU5powFXDhCwa"
    model_id: str = "eleven_multilingual_v2"
    output_format: str = "mp3_44100_128"


class AzureConfig(BaseModel):
    enabled: bool = False
    subscription_key: str = ""
    region: str = "westeurope"
    default_voice: str = "de-DE-KatjaNeural"


class PollyConfig(BaseModel):
    enabled: bool = False
    region: str = "eu-central-1"
    default_voice: str = "Vicki"


class PiperConfig(BaseModel):
    enabled: bool = False
    model_path: str = "/models/de_DE-thorsten-high.onnx"


class BackendsConfig(BaseModel):
    elevenlabs: ElevenLabsConfig = Field(default_factory=ElevenLabsConfig)
    azure: AzureConfig = Field(default_factory=AzureConfig)
    polly: PollyConfig = Field(default_factory=PollyConfig)
    piper: PiperConfig = Field(default_factory=PiperConfig)

    def get(self, name: str) -> Any:
        return getattr(self, name, None)


# ---------------------------------------------------------------------------
# Other configs
# ---------------------------------------------------------------------------


class ServiceConfig(BaseModel):
    api_key: str = ""
    host: str = "0.0.0.0"
    port: int = 8080
    worker_concurrency: int = 3


class StorageConfig(BaseModel):
    path: str = "/data/audio"
    public_base_url: str = "https://tts.service/audio"
    cleanup_after_days: int = 7


class QueueConfig(BaseModel):
    backend: str = "sqlite"
    sqlite_path: str = "/data/jobs.db"


class WebhookConfig(BaseModel):
    signing_secret: str = ""
    timeout_seconds: int = 10
    retry_attempts: int = 3


class WorkerConfig(BaseModel):
    polling_interval_seconds: float = 2.0
    max_retries: int = 3
    synthesize_timeout_seconds: float = 60.0


# ---------------------------------------------------------------------------
# Root config
# ---------------------------------------------------------------------------


class Config(BaseModel):
    service: ServiceConfig = Field(default_factory=ServiceConfig)
    default_backend: str = "elevenlabs"
    backend_fallback_order: list[str] = Field(default_factory=lambda: ["elevenlabs"])
    backends: BackendsConfig = Field(default_factory=BackendsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)
    worker: WorkerConfig = Field(default_factory=WorkerConfig)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_ENV_RE = re.compile(r"\$\{([^}]+)\}")


def _expand_env(value: Any) -> Any:
    """Recursively expand ${VAR} placeholders in strings."""
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    return value


def load_config(path: str | Path | None = None) -> Config:
    """Load configuration from a YAML file with env-var expansion.

    Falls back to defaults if the file does not exist (useful for tests).
    """
    if path is None:
        path = Path(__file__).parent.parent / "config.yaml"
    path = Path(path)

    raw: dict[str, Any] = {}
    if path.exists():
        with path.open() as f:
            raw = yaml.safe_load(f) or {}
        raw = _expand_env(raw)

    return Config(**raw)


# ---------------------------------------------------------------------------
# Singleton for convenience
# ---------------------------------------------------------------------------

_config: Config | None = None


def get_config(path: str | Path | None = None) -> Config:
    global _config
    if _config is None:
        _config = load_config(path)
    return _config


def reset_config() -> None:
    """Reset the singleton (useful in tests)."""
    global _config
    _config = None
