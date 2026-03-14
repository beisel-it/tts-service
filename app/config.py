"""Configuration system for the TTS service.

Supports both the newer worker-focused config shape and the legacy settings
interface used by API/storage tests (`get_settings`, `reload_settings`).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, SecretStr, model_validator


# ---------------------------------------------------------------------------
# Backend configs
# ---------------------------------------------------------------------------


class ElevenLabsConfig(BaseModel):
    enabled: bool = True
    api_key: str = ""
    default_voice: str = "XB0fDUnXU5powFXDhCwa"
    model_id: str = "eleven_multilingual_v2"
    output_format: str = "mp3_44100_128"

    @property
    def default_voice_id(self) -> str:
        return self.default_voice


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
    default_backend: str = "elevenlabs"
    enabled: list[str] = Field(default_factory=lambda: ["elevenlabs"])
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
    host: str = "0.0.0.0"
    port: int = 8080
    worker_concurrency: int = 3


class StorageConfig(BaseModel):
    path: str = "/data/audio"
    public_base_url: str = "https://tts.service"
    audio_prefix: str = "audio"
    cleanup_after_days: int = 7


class QueueConfig(BaseModel):
    backend: str = "sqlite"
    sqlite_path: str = "/data/jobs.db"
    default_fetch_limit: int = 10


class WebhookConfig(BaseModel):
    enabled: bool = True
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
    # Legacy/public API settings expected by app.api + tests
    service_name: str = "tts-service"
    api_base_url: str = "http://localhost:8000"
    sqlite_path: str = "/data/jobs.db"
    max_text_length: int = 5000
    api_key: SecretStr | None = None

    # Newer worker/runtime sections
    default_backend: str = "elevenlabs"
    backend_fallback_order: list[str] = Field(default_factory=lambda: ["elevenlabs"])
    service: ServiceConfig = Field(default_factory=ServiceConfig)
    backends: BackendsConfig = Field(default_factory=BackendsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)
    worker: WorkerConfig = Field(default_factory=WorkerConfig)

    @model_validator(mode="after")
    def _sync_legacy_and_nested(self) -> "Config":
        # Keep default backend consistent across legacy/new paths.
        self.default_backend = self.backends.default_backend or self.default_backend
        self.backends.default_backend = self.default_backend

        # Keep sqlite path consistent across legacy/new paths.
        if self.queue.sqlite_path and self.queue.sqlite_path != "/data/jobs.db":
            self.sqlite_path = self.queue.sqlite_path
        else:
            self.queue.sqlite_path = self.sqlite_path

        if not self.backend_fallback_order:
            self.backend_fallback_order = [self.default_backend]
        return self

    def get_audio_url(self, text_hash: str) -> str:
        base = self.storage.public_base_url.rstrip("/")
        prefix = self.storage.audio_prefix.strip("/")
        return f"{base}/{prefix}/{text_hash[:8]}/{text_hash}.mp3"


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


def _parse_scalar(value: str) -> Any:
    lowered = value.lower().strip()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"none", "null"}:
        return None
    # int/float coercion for env overrides
    try:
        if "." in lowered:
            return float(lowered)
        return int(lowered)
    except ValueError:
        return value


def _set_nested(data: dict[str, Any], parts: list[str], value: Any) -> None:
    node: dict[str, Any] = data
    for part in parts[:-1]:
        existing = node.get(part)
        if not isinstance(existing, dict):
            existing = {}
            node[part] = existing
        node = existing
    node[parts[-1]] = value


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    # Flat legacy shortcuts
    if "TTS_SQLITE_PATH" in os.environ:
        raw["sqlite_path"] = os.environ["TTS_SQLITE_PATH"]
    if "TTS_API_KEY" in os.environ:
        raw["api_key"] = os.environ["TTS_API_KEY"]

    # Nested overrides with double-underscore notation.
    # Example: TTS_STORAGE__PUBLIC_BASE_URL -> storage.public_base_url
    for key, value in os.environ.items():
        if not key.startswith("TTS_") or "__" not in key:
            continue
        path = key[4:].lower().split("__")
        _set_nested(raw, path, _parse_scalar(value))

    return raw


def load_config(path: str | Path | None = None) -> Config:
    """Load configuration from YAML + .env + environment overrides."""
    if path is None:
        path = os.environ.get("TTS_CONFIG_FILE")
    if path is None:
        path = Path(__file__).parent.parent / "config.yaml"

    path = Path(path)
    raw: dict[str, Any] = {}

    # Load .env from cwd by convention used in tests.
    _load_dotenv(path.parent / ".env")

    if path.exists():
        with path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        raw = _expand_env(raw)

    raw = _apply_env_overrides(raw)
    return Config(**raw)


# ---------------------------------------------------------------------------
# Singleton convenience API
# ---------------------------------------------------------------------------

_config: Config | None = None


def get_config(path: str | Path | None = None) -> Config:
    global _config
    if _config is None:
        _config = load_config(path)
    return _config


def get_settings(path: str | Path | None = None) -> Config:
    return get_config(path)


def reset_config() -> None:
    global _config
    _config = None


def reload_settings(path: str | Path | None = None) -> Config:
    reset_config()
    return get_settings(path)
