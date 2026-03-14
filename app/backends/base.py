"""Base classes and exception hierarchy for TTS backends.

See ARCHITECTURE.md §4 for the interface specification.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Exception hierarchy (E2)
# ---------------------------------------------------------------------------


class TTSError(Exception):
    """Base exception for all TTS backend errors."""


class RecoverableError(TTSError):
    """Transient error — safe to retry with the same or another backend."""


class NonRecoverableError(TTSError):
    """Permanent error — retrying will not help; fail the job immediately."""


class NetworkError(RecoverableError):
    """Connection or network-level failure."""


class RateLimitError(RecoverableError):
    """Backend rate-limit (HTTP 429). Contains Retry-After hint."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class TemporaryServiceError(RecoverableError):
    """Backend temporarily unavailable (5xx)."""


class AuthenticationError(NonRecoverableError):
    """Invalid or missing API key (HTTP 401/403)."""


class BadRequestError(NonRecoverableError):
    """Malformed request — bad voice_id, text, or parameters (HTTP 400)."""


class InvalidVoiceError(NonRecoverableError):
    """The requested voice_id is not available on this backend."""


class InvalidTextError(NonRecoverableError):
    """The text content cannot be synthesised (too long, empty, etc.)."""


# ---------------------------------------------------------------------------
# VoiceInfo
# ---------------------------------------------------------------------------


@dataclass
class VoiceInfo:
    voice_id: str
    name: str
    language: str = ""
    gender: str = ""
    description: str = ""
    category: str = ""


# ---------------------------------------------------------------------------
# TTSBackend ABC
# ---------------------------------------------------------------------------


class TTSBackend(ABC):
    """Abstract base class every TTS backend must implement."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_format: str = "mp3_44100_128",
    ) -> bytes:
        """Synthesise *text* and return raw audio bytes.

        Args:
            text: The text to synthesise (1–5000 characters).
            voice_id: Backend-specific voice identifier.
            output_format: Audio format string (backend-specific default).

        Returns:
            Raw audio bytes (e.g. MP3).

        Raises:
            RecoverableError: Transient failure — caller may retry.
            NonRecoverableError: Permanent failure — caller should give up.
            ValueError: Invalid input parameters.
        """

    @abstractmethod
    async def list_voices(self) -> list[VoiceInfo]:
        """Return available voices for this backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique backend identifier (e.g. 'elevenlabs', 'azure')."""
