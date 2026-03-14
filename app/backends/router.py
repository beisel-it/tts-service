"""Backend Router — configuration-based TTS backend selection.

See Task E1 for the specification.

The router instantiates backends lazily and caches instances. It supports
dependency injection of mock backends for testing.
"""

from __future__ import annotations

import logging
from typing import Any

from app.backends.base import TTSBackend, VoiceInfo
from app.config import Config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Router exceptions
# ---------------------------------------------------------------------------


class InvalidBackendError(Exception):
    """Requested backend is unknown or disabled in configuration."""


class BackendInitError(Exception):
    """Backend could not be initialised (e.g. missing API key)."""


class BackendUnavailableError(Exception):
    """Backend is configured but currently unreachable."""


# ---------------------------------------------------------------------------
# BackendRouter
# ---------------------------------------------------------------------------

_KNOWN_BACKENDS = ("elevenlabs", "azure", "polly", "piper")


class BackendRouter:
    """Selects and lazily initialises TTS backends based on configuration.

    Args:
        config: Loaded application configuration.
        logger_: Optional logger instance (defaults to module logger).
        backend_overrides: Map of backend name → pre-built TTSBackend instances.
            Useful for injecting mocks in tests.
    """

    def __init__(
        self,
        config: Config,
        logger_: logging.Logger | None = None,
        backend_overrides: dict[str, TTSBackend] | None = None,
    ) -> None:
        self._config = config
        self._log = logger_ or logger
        self._backends: dict[str, TTSBackend] = dict(backend_overrides or {})
        self._log.info("Initializing Backend Router")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_backend(self, backend_name: str | None = None) -> TTSBackend:
        """Return a (cached) TTSBackend instance.

        Args:
            backend_name: Backend identifier. Defaults to
                ``config.default_backend`` when *None*.

        Returns:
            A ready-to-use TTSBackend instance.

        Raises:
            InvalidBackendError: *backend_name* is unknown or disabled.
            BackendInitError: Backend could not be initialised.
        """
        name = backend_name or self._config.default_backend

        if name in self._backends:
            self._log.debug("Using cached backend '%s'", name)
            return self._backends[name]

        self._validate_backend(name)

        self._log.info("Loading backend '%s'", name)
        backend = self._create_backend(name)
        self._backends[name] = backend
        return backend

    def list_available_backends(self) -> dict[str, list[VoiceInfo]]:
        """Return voice lists for all enabled (cached) backends.

        Only backends that have already been instantiated are queried.
        To force loading all enabled backends first, call
        ``get_backend(name)`` for each.
        """
        result: dict[str, list[VoiceInfo]] = {}
        for name, backend in self._backends.items():
            try:
                result[name] = backend.list_voices()
            except NotImplementedError:
                result[name] = []
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_backend(self, name: str) -> None:
        """Raise InvalidBackendError if *name* is not enabled."""
        if name not in _KNOWN_BACKENDS:
            self._log.warning("Backend '%s' not available (unknown)", name)
            raise InvalidBackendError(
                f"Backend '{name}' not configured or disabled. "
                f"Known backends: {', '.join(_KNOWN_BACKENDS)}"
            )

        backend_cfg = self._config.backends.get(name)
        if backend_cfg is None:
            raise InvalidBackendError(f"Backend '{name}' has no configuration entry")

        enabled: Any = getattr(backend_cfg, "enabled", True)
        if not enabled:
            self._log.warning("Backend '%s' not available (disabled)", name)
            raise InvalidBackendError(
                f"Backend '{name}' is disabled in configuration. "
                "Set backends.<name>.enabled=true to enable it."
            )

    def _create_backend(self, name: str) -> TTSBackend:
        """Instantiate the backend identified by *name*."""
        try:
            if name == "elevenlabs":
                from app.backends.elevenlabs import create_elevenlabs_backend
                return create_elevenlabs_backend(self._config.backends.elevenlabs)
            if name == "azure":
                from app.backends.azure import create_azure_backend
                return create_azure_backend(self._config.backends.azure)
            if name == "polly":
                from app.backends.polly import create_polly_backend
                return create_polly_backend(self._config.backends.polly)
            if name == "piper":
                from app.backends.piper import create_piper_backend
                return create_piper_backend(self._config.backends.piper)
        except (ValueError, RuntimeError) as exc:
            raise BackendInitError(
                f"Failed to initialize backend '{name}': {exc}"
            ) from exc

        # Should never be reached because _validate_backend filters unknowns.
        raise InvalidBackendError(f"Backend '{name}' has no factory implementation")
