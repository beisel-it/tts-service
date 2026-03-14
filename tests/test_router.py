"""Tests for the backend router (Task E1)."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from app.backends.base import TTSBackend, VoiceInfo
from app.backends.router import BackendInitError, BackendRouter, InvalidBackendError
from app.config import Config, ElevenLabsConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**kwargs) -> Config:
    defaults = {"default_backend": "elevenlabs"}
    defaults.update(kwargs)
    return Config(**defaults)


def _mock_backend(name: str = "mock") -> TTSBackend:
    backend = MagicMock(spec=TTSBackend)
    backend.name = name
    backend.list_voices.return_value = [VoiceInfo(voice_id="v1", name="Voice One")]
    return backend


# ---------------------------------------------------------------------------
# Default backend
# ---------------------------------------------------------------------------


def test_get_backend_returns_default_when_none():
    mock = _mock_backend("elevenlabs")
    router = BackendRouter(
        _make_config(default_backend="elevenlabs"),
        backend_overrides={"elevenlabs": mock},
    )
    backend = router.get_backend(None)
    assert backend is mock


def test_get_backend_none_uses_config_default():
    mock = _mock_backend("elevenlabs")
    router = BackendRouter(
        _make_config(default_backend="elevenlabs"),
        backend_overrides={"elevenlabs": mock},
    )
    assert router.get_backend() is mock


# ---------------------------------------------------------------------------
# Explicit backend name
# ---------------------------------------------------------------------------


def test_get_backend_by_name():
    el = _mock_backend("elevenlabs")
    router = BackendRouter(
        _make_config(),
        backend_overrides={"elevenlabs": el},
    )
    assert router.get_backend("elevenlabs") is el


# ---------------------------------------------------------------------------
# Invalid / disabled backend
# ---------------------------------------------------------------------------


def test_get_backend_unknown_raises_invalid_backend_error():
    router = BackendRouter(_make_config())
    with pytest.raises(InvalidBackendError, match="nonexistent"):
        router.get_backend("nonexistent")


def test_get_backend_disabled_raises_invalid_backend_error():
    from app.config import AzureConfig, BackendsConfig
    cfg = Config(
        default_backend="elevenlabs",
        backends=BackendsConfig(azure=AzureConfig(enabled=False)),
    )
    router = BackendRouter(cfg)
    with pytest.raises(InvalidBackendError, match="azure"):
        router.get_backend("azure")


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def test_get_backend_returns_same_instance_on_second_call():
    mock = _mock_backend("elevenlabs")
    router = BackendRouter(
        _make_config(),
        backend_overrides={"elevenlabs": mock},
    )
    first = router.get_backend("elevenlabs")
    second = router.get_backend("elevenlabs")
    assert first is second


def test_backend_not_in_cache_before_first_access():
    router = BackendRouter(
        _make_config(),
        backend_overrides={},
    )
    # No backends loaded yet
    assert "elevenlabs" not in router._backends


# ---------------------------------------------------------------------------
# Mock override
# ---------------------------------------------------------------------------


def test_mock_override_is_used_instead_of_real_backend():
    mock = _mock_backend("elevenlabs")
    router = BackendRouter(
        _make_config(),
        backend_overrides={"elevenlabs": mock},
    )
    result = router.get_backend("elevenlabs")
    assert result is mock


# ---------------------------------------------------------------------------
# list_available_backends
# ---------------------------------------------------------------------------


def test_list_available_backends_returns_voices():
    mock = _mock_backend("elevenlabs")
    router = BackendRouter(
        _make_config(),
        backend_overrides={"elevenlabs": mock},
    )
    router.get_backend("elevenlabs")  # populate cache
    result = router.list_available_backends()
    assert "elevenlabs" in result
    assert len(result["elevenlabs"]) == 1
    assert result["elevenlabs"][0].voice_id == "v1"


def test_list_available_backends_empty_when_no_cache():
    router = BackendRouter(_make_config(), backend_overrides={})
    # Without ever calling get_backend, cache is empty
    assert router.list_available_backends() == {}


# ---------------------------------------------------------------------------
# BackendInitError
# ---------------------------------------------------------------------------


def test_backend_init_error_raised_on_missing_api_key():
    from app.config import BackendsConfig, ElevenLabsConfig
    cfg = Config(
        default_backend="elevenlabs",
        backends=BackendsConfig(elevenlabs=ElevenLabsConfig(enabled=True, api_key="")),
    )
    router = BackendRouter(cfg)
    with pytest.raises(BackendInitError, match="elevenlabs"):
        router.get_backend("elevenlabs")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def test_router_logs_init(caplog):
    with caplog.at_level(logging.INFO, logger="app.backends.router"):
        BackendRouter(_make_config())
    assert any("Initializing Backend Router" in r.message for r in caplog.records)


def test_router_logs_loading_backend(caplog):
    mock = _mock_backend("elevenlabs")
    router = BackendRouter(_make_config(), backend_overrides={})
    # Override after construction to test lazy load log
    router._backends["elevenlabs"] = mock
    with caplog.at_level(logging.DEBUG, logger="app.backends.router"):
        router.get_backend("elevenlabs")
    # The backend was already in cache, so "Using cached backend" should appear
    assert any("cached" in r.message.lower() for r in caplog.records)
