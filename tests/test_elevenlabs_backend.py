"""Tests for the ElevenLabs TTS backend (Task D1)."""
from __future__ import annotations

import pytest
import respx
import httpx

from app.backends.elevenlabs import ElevenLabsBackend
from app.backends.base import AuthenticationError, BadRequestError, NetworkError, RateLimitError
from app.config import ElevenLabsConfig


def _config(api_key: str = "test-key", model_id: str = "eleven_multilingual_v2", output_format: str = "mp3_44100_128") -> ElevenLabsConfig:
    return ElevenLabsConfig(api_key=api_key, model_id=model_id, output_format=output_format)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def test_init_requires_api_key():
    with pytest.raises(ValueError, match="API key"):
        ElevenLabsBackend(_config(api_key=""))


def test_name():
    backend = ElevenLabsBackend(_config())
    assert backend.name == "elevenlabs"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesize_rejects_empty_text():
    backend = ElevenLabsBackend(_config())
    with pytest.raises(ValueError, match="empty"):
        await backend.synthesize(text="", voice_id="voice1")


@pytest.mark.asyncio
async def test_synthesize_rejects_oversized_text():
    backend = ElevenLabsBackend(_config())
    with pytest.raises(ValueError, match="5000"):
        await backend.synthesize(text="x" * 5001, voice_id="voice1")


@pytest.mark.asyncio
async def test_synthesize_rejects_empty_voice_id():
    backend = ElevenLabsBackend(_config())
    with pytest.raises(ValueError, match="voice_id"):
        await backend.synthesize(text="hello", voice_id="")


# ---------------------------------------------------------------------------
# Successful synthesis
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_synthesize_success():
    audio_data = b"FAKE_MP3_BYTES"
    voice_id = "XB0fDUnXU5powFXDhCwa"
    respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}").mock(
        return_value=httpx.Response(200, content=audio_data)
    )

    backend = ElevenLabsBackend(_config())
    result = await backend.synthesize(text="Hello world", voice_id=voice_id)
    assert result == audio_data


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_sends_correct_headers_and_body():
    voice_id = "test-voice"
    route = respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}").mock(
        return_value=httpx.Response(200, content=b"bytes")
    )

    backend = ElevenLabsBackend(_config(api_key="my-api-key", model_id="eleven_multilingual_v2"))
    await backend.synthesize(text="Test text", voice_id=voice_id)

    request = route.calls[0].request
    assert request.headers["xi-api-key"] == "my-api-key"
    import json
    body = json.loads(request.content)
    assert body["text"] == "Test text"
    assert body["model_id"] == "eleven_multilingual_v2"


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_uses_output_format_query_param():
    voice_id = "v1"
    route = respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}").mock(
        return_value=httpx.Response(200, content=b"audio")
    )

    backend = ElevenLabsBackend(_config(output_format="mp3_44100_128"))
    await backend.synthesize(text="Hi", voice_id=voice_id, output_format="mp3_22050_32")

    url = str(route.calls[0].request.url)
    assert "output_format=mp3_22050_32" in url


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_synthesize_401_raises_authentication_error():
    voice_id = "v1"
    respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )

    backend = ElevenLabsBackend(_config())
    with pytest.raises(AuthenticationError):
        await backend.synthesize(text="hello", voice_id=voice_id)


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_429_raises_rate_limit_error():
    voice_id = "v1"
    respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}").mock(
        return_value=httpx.Response(429, text="Rate limit", headers={"Retry-After": "30"})
    )

    backend = ElevenLabsBackend(_config())
    with pytest.raises(RateLimitError) as exc_info:
        await backend.synthesize(text="hello", voice_id=voice_id)
    assert exc_info.value.retry_after == 30.0


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_429_without_retry_after():
    voice_id = "v1"
    respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}").mock(
        return_value=httpx.Response(429, text="Rate limit")
    )

    backend = ElevenLabsBackend(_config())
    with pytest.raises(RateLimitError) as exc_info:
        await backend.synthesize(text="hello", voice_id=voice_id)
    assert exc_info.value.retry_after is None


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_400_raises_bad_request_error():
    voice_id = "v1"
    respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}").mock(
        return_value=httpx.Response(400, text="Bad request")
    )

    backend = ElevenLabsBackend(_config())
    with pytest.raises(BadRequestError):
        await backend.synthesize(text="hello", voice_id=voice_id)


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_network_timeout_raises_network_error():
    voice_id = "v1"
    respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}").mock(
        side_effect=httpx.TimeoutException("timed out")
    )

    backend = ElevenLabsBackend(_config())
    with pytest.raises(NetworkError, match="timed out"):
        await backend.synthesize(text="hello", voice_id=voice_id)


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_connection_error_raises_network_error():
    voice_id = "v1"
    respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    backend = ElevenLabsBackend(_config())
    with pytest.raises(NetworkError, match="connection refused"):
        await backend.synthesize(text="hello", voice_id=voice_id)


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_unexpected_status_raises_network_error():
    voice_id = "v1"
    respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}").mock(
        return_value=httpx.Response(503, text="Service unavailable")
    )

    backend = ElevenLabsBackend(_config())
    with pytest.raises(NetworkError, match="503"):
        await backend.synthesize(text="hello", voice_id=voice_id)


# ---------------------------------------------------------------------------
# list_voices
# ---------------------------------------------------------------------------

def test_list_voices_returns_empty_list():
    backend = ElevenLabsBackend(_config())
    assert backend.list_voices() == []
