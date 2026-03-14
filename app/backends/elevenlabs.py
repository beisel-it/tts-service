"""ElevenLabs TTS backend implementation.

See ARCHITECTURE.md §4.1 and Task D1 for the specification.

Endpoint: POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}
Auth:      xi-api-key header
Model:     eleven_multilingual_v2 (configurable)
Output:    mp3_44100_128 (configurable)
"""

from __future__ import annotations

import logging

import httpx

from app.backends.base import (
    AuthenticationError,
    BadRequestError,
    NetworkError,
    RateLimitError,
    TTSBackend,
    VoiceInfo,
)
from app.config import ElevenLabsConfig

logger = logging.getLogger(__name__)

_API_BASE = "https://api.elevenlabs.io/v1"
_MAX_TEXT_LENGTH = 5000


class ElevenLabsBackend(TTSBackend):
    """TTS backend that calls the ElevenLabs REST API.

    Args:
        config: ElevenLabs-specific configuration section.
    """

    def __init__(self, config: ElevenLabsConfig) -> None:
        if not config.api_key:
            raise ValueError(
                "ElevenLabs API key is required. Set ELEVENLABS_API_KEY or "
                "backends.elevenlabs.api_key in config.yaml."
            )
        self._api_key = config.api_key
        self._model_id = config.model_id
        self._default_output_format = config.output_format
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    @property
    def name(self) -> str:
        return "elevenlabs"

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_format: str | None = None,
    ) -> bytes:
        """Synthesise text via the ElevenLabs API and return raw MP3 bytes.

        Args:
            text: Text to synthesise (1–5000 characters).
            voice_id: ElevenLabs voice identifier.
            output_format: Audio format; defaults to configured value.

        Returns:
            Raw audio bytes (MP3).

        Raises:
            ValueError: Invalid input (empty text, text too long, empty voice_id).
            AuthenticationError: API key rejected (HTTP 401).
            RateLimitError: Rate limited (HTTP 429).
            BadRequestError: Invalid voice/text (HTTP 400).
            NetworkError: Connection failure.
        """
        if not text:
            raise ValueError("text must not be empty")
        if len(text) > _MAX_TEXT_LENGTH:
            raise ValueError(
                f"text length {len(text)} exceeds maximum of {_MAX_TEXT_LENGTH} characters"
            )
        if not voice_id:
            raise ValueError("voice_id must not be empty")

        fmt = output_format or self._default_output_format
        url = f"{_API_BASE}/text-to-speech/{voice_id}"

        logger.debug(
            "ElevenLabs synthesize start",
            extra={"voice_id": voice_id, "text_length": len(text)},
        )

        try:
            response = await self._client.post(
                url,
                params={"output_format": fmt},
                headers={
                    "xi-api-key": self._api_key,
                    "Content-Type": "application/json",
                },
                json={"text": text, "model_id": self._model_id},
            )
        except httpx.TimeoutException as exc:
            raise NetworkError(f"Request to ElevenLabs timed out: {exc}") from exc
        except httpx.RequestError as exc:
            raise NetworkError(f"Network error calling ElevenLabs: {exc}") from exc

        if response.status_code == 200:
            logger.debug(
                "ElevenLabs synthesize success",
                extra={"voice_id": voice_id, "bytes": len(response.content)},
            )
            return response.content

        body = response.text
        if response.status_code == 401:
            raise AuthenticationError(
                f"ElevenLabs authentication failed (401): {body}"
            )
        if response.status_code == 429:
            retry_after: float | None = None
            try:
                retry_after = float(response.headers.get("Retry-After", ""))
            except (TypeError, ValueError):
                pass
            raise RateLimitError(
                f"ElevenLabs rate limit exceeded (429): {body}",
                retry_after=retry_after,
            )
        if response.status_code == 400:
            raise BadRequestError(
                f"ElevenLabs bad request (400): {body}"
            )
        raise NetworkError(
            f"ElevenLabs returned unexpected status {response.status_code}: {body}"
        )

    def list_voices(self) -> list[VoiceInfo]:
        """Return an empty list (voice listing is task D2)."""
        return []

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


def create_elevenlabs_backend(config: ElevenLabsConfig) -> ElevenLabsBackend:
    """Factory function called by BackendRouter."""
    return ElevenLabsBackend(config)
