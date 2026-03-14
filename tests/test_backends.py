"""Tests for backend stubs — F1 (Azure, Piper) and F2 (Polly).

Verifies:
- All stubs can be instantiated.
- name property returns the expected string.
- synthesize() and list_voices() raise NotImplementedError.
- BackendRouter correctly creates stubs when enabled.
- Disabled backends raise InvalidBackendError.
"""

from __future__ import annotations

import pytest

from app.backends.azure import AzureBackend
from app.backends.base import get_backend
from app.backends.piper import PiperBackend
from app.backends.polly import PollyBackend
from app.backends.router import BackendRouter, InvalidBackendError
from app.config import AzureConfig, BackendsConfig, Config, PiperConfig, PollyConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _azure_backend() -> AzureBackend:
    return AzureBackend(AzureConfig(enabled=True))


def _polly_backend() -> PollyBackend:
    return PollyBackend(PollyConfig(enabled=True))


def _piper_backend() -> PiperBackend:
    return PiperBackend(PiperConfig(enabled=True))


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


def test_azure_backend_instantiates():
    b = _azure_backend()
    assert isinstance(b, AzureBackend)


def test_polly_backend_instantiates():
    b = _polly_backend()
    assert isinstance(b, PollyBackend)


def test_piper_backend_instantiates():
    b = _piper_backend()
    assert isinstance(b, PiperBackend)


# ---------------------------------------------------------------------------
# name property
# ---------------------------------------------------------------------------


def test_azure_name():
    assert _azure_backend().name == "azure"


def test_polly_name():
    assert _polly_backend().name == "polly"


def test_piper_name():
    assert _piper_backend().name == "piper"


# ---------------------------------------------------------------------------
# synthesize raises NotImplementedError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_azure_synthesize_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await _azure_backend().synthesize("text", "voice-id")


@pytest.mark.asyncio
async def test_polly_synthesize_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await _polly_backend().synthesize("text", "voice-id")


@pytest.mark.asyncio
async def test_piper_synthesize_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await _piper_backend().synthesize("text", "voice-id")


# ---------------------------------------------------------------------------
# list_voices raises NotImplementedError
# ---------------------------------------------------------------------------


def test_azure_list_voices_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        _azure_backend().list_voices()


def test_polly_list_voices_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        _polly_backend().list_voices()


def test_piper_list_voices_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        _piper_backend().list_voices()


# ---------------------------------------------------------------------------
# BackendRouter integration — stubs can be injected and retrieved
# ---------------------------------------------------------------------------


def test_router_can_use_injected_azure_backend():
    backend = _azure_backend()
    cfg = Config(
        default_backend="azure",
        backends=BackendsConfig(azure=AzureConfig(enabled=True)),
    )
    router = BackendRouter(cfg, backend_overrides={"azure": backend})
    assert router.get_backend("azure") is backend


def test_router_can_use_injected_polly_backend():
    backend = _polly_backend()
    cfg = Config(
        default_backend="polly",
        backends=BackendsConfig(polly=PollyConfig(enabled=True)),
    )
    router = BackendRouter(cfg, backend_overrides={"polly": backend})
    assert router.get_backend("polly") is backend


def test_router_can_use_injected_piper_backend():
    backend = _piper_backend()
    cfg = Config(
        default_backend="piper",
        backends=BackendsConfig(piper=PiperConfig(enabled=True)),
    )
    router = BackendRouter(cfg, backend_overrides={"piper": backend})
    assert router.get_backend("piper") is backend


# ---------------------------------------------------------------------------
# Disabled backend → InvalidBackendError
# ---------------------------------------------------------------------------


def test_disabled_azure_raises_invalid_backend_error():
    cfg = Config(
        default_backend="elevenlabs",
        backends=BackendsConfig(azure=AzureConfig(enabled=False)),
    )
    router = BackendRouter(cfg)
    with pytest.raises(InvalidBackendError, match="azure"):
        router.get_backend("azure")


def test_disabled_polly_raises_invalid_backend_error():
    cfg = Config(
        default_backend="elevenlabs",
        backends=BackendsConfig(polly=PollyConfig(enabled=False)),
    )
    router = BackendRouter(cfg)
    with pytest.raises(InvalidBackendError, match="polly"):
        router.get_backend("polly")


def test_disabled_piper_raises_invalid_backend_error():
    cfg = Config(
        default_backend="elevenlabs",
        backends=BackendsConfig(piper=PiperConfig(enabled=False)),
    )
    router = BackendRouter(cfg)
    with pytest.raises(InvalidBackendError, match="piper"):
        router.get_backend("piper")


# ---------------------------------------------------------------------------
# __init__.py exports
# ---------------------------------------------------------------------------


def test_backends_package_exports():
    from app.backends import AzureBackend, PollyBackend, PiperBackend, TTSBackend, VoiceInfo  # noqa: F401
    assert issubclass(AzureBackend, TTSBackend)
    assert issubclass(PollyBackend, TTSBackend)
    assert issubclass(PiperBackend, TTSBackend)


def test_get_backend_factory_creates_stub_backend():
    cfg = Config(
        default_backend="polly",
        backends=BackendsConfig(polly=PollyConfig(enabled=True)),
    )
    backend = get_backend("polly", cfg)
    assert isinstance(backend, PollyBackend)


def test_get_backend_factory_disabled_backend_raises_value_error():
    cfg = Config(
        default_backend="azure",
        backends=BackendsConfig(azure=AzureConfig(enabled=False)),
    )
    with pytest.raises(ValueError, match="Backend 'azure' not enabled or not found"):
        get_backend("azure", cfg)
