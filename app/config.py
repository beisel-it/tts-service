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


class ElevenLabsSettings(BaseModel):
    api_key: SecretStr | None = None
    default_voice: str = "de-default"
    model_id: str = "eleven_multilingual_v2"


class BackendsSettings(BaseModel):
    default_backend: str = "elevenlabs"
    enabled: list[str] = Field(default_factory=lambda: ["elevenlabs"])
    elevenlabs: ElevenLabsSettings = Field(default_factory=ElevenLabsSettings)


class StorageSettings(BaseModel):
    public_base_url: str = "http://localhost:8000"
    audio_prefix: str = "audio"
    path: str = "/data/audio"
    cleanup_after_days: int = 7


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

    storage: StorageSettings = Field(default_factory=StorageSettings)
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


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
