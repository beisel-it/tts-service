from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


# ---------------------------------------------------------------------------
# Typed backend config classes (used by BackendRouter + backend implementations)
# ---------------------------------------------------------------------------


class ElevenLabsConfig(BaseModel):
    """ElevenLabs backend configuration (ARCHITECTURE.md §4.1)."""

    enabled: bool = True
    api_key: str = ""
    model_id: str = "eleven_multilingual_v2"
    output_format: str = "mp3_44100_128"


class AzureConfig(BaseModel):
    """Azure Cognitive Services TTS configuration (ARCHITECTURE.md §4.2)."""

    enabled: bool = False


class PollyConfig(BaseModel):
    """Amazon Polly TTS configuration (ARCHITECTURE.md §4.3)."""

    enabled: bool = False


class PiperConfig(BaseModel):
    """Piper self-hosted TTS configuration (ARCHITECTURE.md §4.4)."""

    enabled: bool = False


class BackendsConfig(BaseModel):
    """Container for all backend configurations, used by BackendRouter."""

    elevenlabs: ElevenLabsConfig = Field(default_factory=ElevenLabsConfig)
    azure: AzureConfig = Field(default_factory=AzureConfig)
    polly: PollyConfig = Field(default_factory=PollyConfig)
    piper: PiperConfig = Field(default_factory=PiperConfig)

    def get(self, name: str) -> ElevenLabsConfig | AzureConfig | PollyConfig | PiperConfig | None:
        """Return the config section for *name*, or None if unknown."""
        return getattr(self, name, None)


class StorageConfig(BaseModel):
    """Runtime storage config used by LocalStorage and worker."""

    public_base_url: str = "http://localhost:8000"
    audio_prefix: str = "audio"
    path: str = "/data/audio"
    cleanup_after_days: int = 7


class QueueConfig(BaseModel):
    """Runtime queue config used by worker."""

    sqlite_path: str = "/data/jobs.db"
    default_fetch_limit: int = 10


class WorkerConfig(BaseModel):
    """Runtime worker config used by worker."""

    polling_interval_seconds: float = 1.0
    max_retries: int = 3
    synthesize_timeout_seconds: int = 60


class Config(BaseModel):
    """Application config consumed by worker/router and tests."""

    default_backend: str = "elevenlabs"
    backend_fallback_order: list[str] = Field(default_factory=list)
    backends: BackendsConfig = Field(default_factory=BackendsConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    worker: WorkerConfig = Field(default_factory=WorkerConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)


# ---------------------------------------------------------------------------
# AppSettings — full application settings from YAML / env
# ---------------------------------------------------------------------------


class ElevenLabsSettings(BaseModel):
    enabled: bool = True
    api_key: SecretStr | None = None
    default_voice: str = "de-default"
    model_id: str = "eleven_multilingual_v2"
    output_format: str = "mp3_44100_128"


class AzureSettings(BaseModel):
    enabled: bool = False


class PollySettings(BaseModel):
    enabled: bool = False


class PiperSettings(BaseModel):
    enabled: bool = False


class BackendsSettings(BaseModel):
    default_backend: str = "elevenlabs"
    enabled: list[str] = Field(default_factory=lambda: ["elevenlabs"])
    elevenlabs: ElevenLabsSettings = Field(default_factory=ElevenLabsSettings)
    azure: AzureSettings = Field(default_factory=AzureSettings)
    polly: PollySettings = Field(default_factory=PollySettings)
    piper: PiperSettings = Field(default_factory=PiperSettings)


class QueueSettings(BaseModel):
    default_fetch_limit: int = 10


class WebhookSettings(BaseModel):
    enabled: bool = True
    timeout_seconds: int = 10
    retry_attempts: int = 3
    signing_secret: SecretStr | None = None


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TTS_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
        nested_model_default_partial_update=True,
    )

    service_name: str = "tts-service"
    api_base_url: str = "http://localhost:8000"
    sqlite_path: str = "/data/jobs.db"
    max_text_length: int = 5000
    api_key: SecretStr | None = None

    storage: StorageConfig = Field(default_factory=StorageConfig)
    queue: QueueSettings = Field(default_factory=QueueSettings)
    webhook: WebhookSettings = Field(default_factory=WebhookSettings)
    backends: BackendsSettings = Field(default_factory=BackendsSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        config_path = Path(os.environ.get("TTS_CONFIG_FILE", "config.yaml"))
        yaml_settings = YamlConfigSettingsSource(settings_cls, yaml_file=config_path)

        custom_dotenv = DotEnvSettingsSource(
            settings_cls,
            env_file=config_path.parent / ".env",
            env_file_encoding=settings_cls.model_config.get("env_file_encoding"),
            case_sensitive=settings_cls.model_config.get("case_sensitive"),
            env_prefix=settings_cls.model_config.get("env_prefix"),
            env_prefix_target=settings_cls.model_config.get("env_prefix_target"),
            env_nested_delimiter=settings_cls.model_config.get("env_nested_delimiter"),
            env_nested_max_split=settings_cls.model_config.get("env_nested_max_split"),
            env_ignore_empty=settings_cls.model_config.get("env_ignore_empty"),
            env_parse_none_str=settings_cls.model_config.get("env_parse_none_str"),
            env_parse_enums=settings_cls.model_config.get("env_parse_enums"),
        )

        return (
            init_settings,
            env_settings,
            custom_dotenv,
            yaml_settings,
            file_secret_settings,
        )

    def get_audio_url(self, text_hash: str) -> str:
        base = self.storage.public_base_url.rstrip("/")
        prefix = self.storage.audio_prefix.strip("/")
        return f"{base}/{prefix}/{text_hash[:8]}/{text_hash}.mp3"


def reload_settings() -> None:
    get_settings.cache_clear()


# Alias used in tests and conftest
reset_config = reload_settings


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()


def _backend_enabled(name: str, explicit_enabled: bool, enabled_list: list[str]) -> bool:
    return explicit_enabled or (name in enabled_list)


def build_router_config(settings: AppSettings) -> Config:
    """Convert AppSettings into a Config suitable for BackendRouter."""
    enabled_list = settings.backends.enabled
    el = settings.backends.elevenlabs

    return Config(
        default_backend=settings.backends.default_backend,
        backend_fallback_order=[settings.backends.default_backend],
        backends=BackendsConfig(
            elevenlabs=ElevenLabsConfig(
                enabled=_backend_enabled("elevenlabs", el.enabled, enabled_list),
                api_key=el.api_key.get_secret_value() if el.api_key else "",
                model_id=el.model_id,
                output_format=el.output_format,
            ),
            azure=AzureConfig(
                enabled=_backend_enabled("azure", settings.backends.azure.enabled, enabled_list)
            ),
            polly=PollyConfig(
                enabled=_backend_enabled("polly", settings.backends.polly.enabled, enabled_list)
            ),
            piper=PiperConfig(
                enabled=_backend_enabled("piper", settings.backends.piper.enabled, enabled_list)
            ),
        ),
        queue=QueueConfig(sqlite_path=settings.sqlite_path, default_fetch_limit=settings.queue.default_fetch_limit),
        worker=WorkerConfig(),
        storage=StorageConfig(
            public_base_url=settings.storage.public_base_url,
            audio_prefix=settings.storage.audio_prefix,
            path=settings.storage.path,
            cleanup_after_days=settings.storage.cleanup_after_days,
        ),
    )


def load_config() -> Config:
    """Compatibility loader for worker entrypoints/tests."""
    return build_router_config(get_settings())
