"""ElevenLabs TTS backend implementation (D1/D2/D3)."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable

import httpx

from app.backends.base import (
    AuthenticationError,
    NetworkError,
    RateLimitError,
    RecoverableError,
    TTSBackend,
    TemporaryServiceError,
    VoiceInfo,
)
from app.config import ElevenLabsConfig

logger = logging.getLogger(__name__)

_API_BASE = "https://api.elevenlabs.io/v1"
_MAX_TEXT_LENGTH = 5000

_NETWORK_MAX_RETRIES = 3
_NETWORK_BASE_DELAY = 0.5
_API_MAX_RETRIES = 3
_API_BASE_DELAY = 1.0
_RATE_LIMIT_MAX_RETRIES = 1
_DEFAULT_RETRY_AFTER = 60.0
_VOICES_CACHE_TTL = 24 * 60 * 60

_LANGUAGE_MAP: dict[str, str] = {
    "english": "en",
    "german": "de",
    "french": "fr",
    "spanish": "es",
    "italian": "it",
    "portuguese": "pt",
    "dutch": "nl",
    "polish": "pl",
    "russian": "ru",
    "japanese": "ja",
    "chinese": "zh",
    "korean": "ko",
    "arabic": "ar",
    "turkish": "tr",
    "swedish": "sv",
    "danish": "da",
    "norwegian": "no",
    "finnish": "fi",
    "czech": "cs",
    "romanian": "ro",
    "hungarian": "hu",
    "bulgarian": "bg",
    "croatian": "hr",
    "slovak": "sk",
    "ukrainian": "uk",
    "greek": "el",
    "hindi": "hi",
    "indonesian": "id",
    "malay": "ms",
    "vietnamese": "vi",
    "thai": "th",
    "filipino": "tl",
}


class ElevenLabsAuthError(AuthenticationError):
    """401/403 from ElevenLabs; permanent failure."""


class ElevenLabsRateLimitError(RateLimitError):
    """429 from ElevenLabs; includes Retry-After hint."""


class ElevenLabsAPIError(TemporaryServiceError):
    """Non-auth API errors from ElevenLabs (4xx/5xx)."""


class ElevenLabsNetworkError(NetworkError):
    """Network-level failures while calling ElevenLabs."""


class ElevenLabsBackend(TTSBackend):
    def __init__(self, config: ElevenLabsConfig) -> None:
        if not config.api_key:
            raise ValueError(
                "ElevenLabs API key is required. Set ELEVENLABS_API_KEY or "
                "backends.elevenlabs.api_key in config.yaml."
            )
        self._api_key = config.api_key
        self._model_id = config.model_id
        self._default_output_format = config.output_format
        self._pron_dict_locators = []
        if config.pronunciation_dictionary_id and config.pronunciation_dictionary_version_id:
            self._pron_dict_locators = [
                {
                    "pronunciation_dictionary_id": config.pronunciation_dictionary_id,
                    "version_id": config.pronunciation_dictionary_version_id,
                }
            ]
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        self._voices_cache: list[VoiceInfo] | None = None
        self._voices_cache_time: float = 0.0

    @property
    def name(self) -> str:
        return "elevenlabs"

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_format: str | None = None,
        pronunciation_dictionary_locators: list[dict[str, str]] | None = None,
    ) -> bytes:
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

        response = await self._request_with_retry(
            operation="synthesize",
            request_fn=lambda: self._client.post(
                url,
                params={"output_format": fmt},
                headers={
                    "xi-api-key": self._api_key,
                    "Content-Type": "application/json",
                },
                json={"text": text, "model_id": self._model_id, "pronunciation_dictionary_locators": (pronunciation_dictionary_locators if pronunciation_dictionary_locators is not None else self._pron_dict_locators)},
            ),
        )
        return response.content

    async def list_voices(self) -> list[VoiceInfo]:
        now = time.monotonic()
        if self._voices_cache is None or (now - self._voices_cache_time) >= _VOICES_CACHE_TTL:
            response = await self._request_with_retry(
                operation="list_voices",
                request_fn=lambda: self._client.get(
                    f"{_API_BASE}/voices",
                    headers={"xi-api-key": self._api_key},
                ),
            )
            self._voices_cache = self._parse_voices_response(response)
            self._voices_cache_time = now

        return sorted(self._voices_cache, key=lambda v: v.name)

    async def _request_with_retry(
        self,
        *,
        operation: str,
        request_fn: Callable[[], Awaitable[httpx.Response]],
    ) -> httpx.Response:
        network_attempt = 0
        api_attempt = 0
        rate_limit_attempt = 0

        while True:
            try:
                response = await request_fn()
            except httpx.TimeoutException as exc:
                err = ElevenLabsNetworkError(f"ElevenLabs timeout during {operation}: {exc}")
                if network_attempt >= _NETWORK_MAX_RETRIES:
                    logger.warning("%s final failure: %s", operation, err)
                    raise err from exc
                delay = _NETWORK_BASE_DELAY * (2**network_attempt) + random.uniform(0, 1)
                logger.warning(
                    "%s network retry %d/%d in %.2fs: %s",
                    operation,
                    network_attempt + 1,
                    _NETWORK_MAX_RETRIES,
                    delay,
                    err,
                )
                network_attempt += 1
                await asyncio.sleep(delay)
                continue
            except httpx.RequestError as exc:
                err = ElevenLabsNetworkError(f"ElevenLabs network error during {operation}: {exc}")
                if network_attempt >= _NETWORK_MAX_RETRIES:
                    logger.warning("%s final failure: %s", operation, err)
                    raise err from exc
                delay = _NETWORK_BASE_DELAY * (2**network_attempt) + random.uniform(0, 1)
                logger.warning(
                    "%s network retry %d/%d in %.2fs: %s",
                    operation,
                    network_attempt + 1,
                    _NETWORK_MAX_RETRIES,
                    delay,
                    err,
                )
                network_attempt += 1
                await asyncio.sleep(delay)
                continue

            status = response.status_code
            if 200 <= status < 300:
                return response

            body = response.text
            if status in (401, 403):
                raise ElevenLabsAuthError(f"ElevenLabs auth failed ({status}): {body}")

            if status == 429:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                err = ElevenLabsRateLimitError(
                    f"ElevenLabs rate limit exceeded (429): {body}",
                    retry_after=retry_after,
                )
                if rate_limit_attempt >= _RATE_LIMIT_MAX_RETRIES:
                    logger.warning("%s final failure: %s", operation, err)
                    raise err
                logger.warning(
                    "%s rate-limit retry %d/%d in %.2fs",
                    operation,
                    rate_limit_attempt + 1,
                    _RATE_LIMIT_MAX_RETRIES,
                    retry_after,
                )
                rate_limit_attempt += 1
                await asyncio.sleep(retry_after)
                continue

            err = ElevenLabsAPIError(
                f"ElevenLabs API error ({status}) during {operation}: {body}"
            )
            if api_attempt >= _API_MAX_RETRIES:
                logger.warning("%s final failure: %s", operation, err)
                raise err

            delay = _API_BASE_DELAY * (2**api_attempt) + random.uniform(0, 1)
            logger.warning(
                "%s API retry %d/%d in %.2fs: status=%d",
                operation,
                api_attempt + 1,
                _API_MAX_RETRIES,
                delay,
                status,
            )
            api_attempt += 1
            await asyncio.sleep(delay)

    def _parse_voices_response(self, response: httpx.Response) -> list[VoiceInfo]:
        try:
            data = response.json()
        except ValueError as exc:
            raise ElevenLabsAPIError("ElevenLabs /voices returned invalid JSON") from exc

        voices: list[VoiceInfo] = []
        for voice in data.get("voices", []):
            voice_id = voice.get("voice_id")
            if not voice_id:
                continue
            labels = voice.get("labels") or {}
            lang_raw = str(labels.get("language") or "").lower().strip()
            language = _LANGUAGE_MAP.get(lang_raw, lang_raw)
            voices.append(
                VoiceInfo(
                    voice_id=voice_id,
                    name=str(voice.get("name") or ""),
                    language=language,
                    gender=str(labels.get("gender") or ""),
                    description=str(voice.get("description") or ""),
                    category=str(voice.get("category") or ""),
                )
            )

        return voices

    async def aclose(self) -> None:
        await self._client.aclose()


def _parse_retry_after(header: str | None) -> float:
    if not header:
        return _DEFAULT_RETRY_AFTER
    try:
        return max(float(header), 0.0)
    except (TypeError, ValueError):
        return _DEFAULT_RETRY_AFTER


def create_elevenlabs_backend(config: ElevenLabsConfig) -> ElevenLabsBackend:
    return ElevenLabsBackend(config)
