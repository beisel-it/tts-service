"""Tests for the ElevenLabs backend (D1/D2/D3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from app.backends.base import AuthenticationError, NetworkError, RateLimitError
from app.backends.elevenlabs import (
    ElevenLabsAPIError,
    ElevenLabsBackend,
    ElevenLabsRateLimitError,
)
from app.config import ElevenLabsConfig


def _config(
    api_key: str = "test-key",
    model_id: str = "eleven_multilingual_v2",
    output_format: str = "mp3_44100_128",
) -> ElevenLabsConfig:
    return ElevenLabsConfig(api_key=api_key, model_id=model_id, output_format=output_format)


def test_init_requires_api_key() -> None:
    with pytest.raises(ValueError, match="API key"):
        ElevenLabsBackend(_config(api_key=""))


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_success() -> None:
    voice_id = "v1"
    respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}").mock(
        return_value=httpx.Response(200, content=b"AUDIO")
    )

    backend = ElevenLabsBackend(_config())
    result = await backend.synthesize(text="Hello", voice_id=voice_id)

    assert result == b"AUDIO"


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_auth_401_is_immediate_no_retry() -> None:
    voice_id = "v1"
    respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )

    backend = ElevenLabsBackend(_config())
    with patch("app.backends.elevenlabs.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        with pytest.raises(AuthenticationError):
            await backend.synthesize(text="hello", voice_id=voice_id)

    sleep_mock.assert_not_called()


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_rate_limit_retries_once_with_retry_after_then_succeeds() -> None:
    voice_id = "v1"
    route = respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}")
    route.side_effect = [
        httpx.Response(429, text="limited", headers={"Retry-After": "1"}),
        httpx.Response(200, content=b"ok"),
    ]

    backend = ElevenLabsBackend(_config())
    with patch("app.backends.elevenlabs.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        result = await backend.synthesize(text="hello", voice_id=voice_id)

    assert result == b"ok"
    sleep_mock.assert_called_once_with(1.0)
    assert len(route.calls) == 2


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_rate_limit_exhausted_raises() -> None:
    voice_id = "v1"
    route = respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}")
    route.side_effect = [
        httpx.Response(429, text="limited", headers={"Retry-After": "1"}),
        httpx.Response(429, text="still-limited", headers={"Retry-After": "1"}),
    ]

    backend = ElevenLabsBackend(_config())
    with patch("app.backends.elevenlabs.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        with pytest.raises(ElevenLabsRateLimitError) as exc:
            await backend.synthesize(text="hello", voice_id=voice_id)

    assert exc.value.retry_after == 1.0
    sleep_mock.assert_called_once_with(1.0)
    assert len(route.calls) == 2


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_network_error_retries_with_backoff() -> None:
    voice_id = "v1"
    route = respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}")
    route.side_effect = [
        httpx.TimeoutException("t1"),
        httpx.ConnectError("c1"),
        httpx.Response(200, content=b"ok"),
    ]

    backend = ElevenLabsBackend(_config())
    with (
        patch("app.backends.elevenlabs.random.uniform", return_value=0.0),
        patch("app.backends.elevenlabs.asyncio.sleep", new_callable=AsyncMock) as sleep_mock,
    ):
        result = await backend.synthesize(text="hello", voice_id=voice_id)

    assert result == b"ok"
    # network backoff: 0.5, 1.0 (jitter patched to 0)
    assert [call.args[0] for call in sleep_mock.call_args_list] == [0.5, 1.0]


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_5xx_retries_then_raises_api_error() -> None:
    voice_id = "v1"
    route = respx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}")
    route.side_effect = [
        httpx.Response(503, text="bad"),
        httpx.Response(503, text="bad"),
        httpx.Response(503, text="bad"),
        httpx.Response(503, text="bad"),
    ]

    backend = ElevenLabsBackend(_config())
    with (
        patch("app.backends.elevenlabs.random.uniform", return_value=0.0),
        patch("app.backends.elevenlabs.asyncio.sleep", new_callable=AsyncMock) as sleep_mock,
    ):
        with pytest.raises(ElevenLabsAPIError):
            await backend.synthesize(text="hello", voice_id=voice_id)

    # API backoff: 1.0, 2.0, 4.0
    assert [call.args[0] for call in sleep_mock.call_args_list] == [1.0, 2.0, 4.0]


@pytest.mark.asyncio
@respx.mock
async def test_list_voices_success_parses_and_sorts() -> None:
    respx.get("https://api.elevenlabs.io/v1/voices").mock(
        return_value=httpx.Response(
            200,
            json={
                "voices": [
                    {
                        "voice_id": "2",
                        "name": "Zeta",
                        "labels": {"language": "german", "gender": "female"},
                        "description": "desc-z",
                    },
                    {
                        "voice_id": "1",
                        "name": "Alpha",
                        "labels": {"language": "english"},
                        "category": "generated",
                    },
                ]
            },
        )
    )

    backend = ElevenLabsBackend(_config())
    voices = await backend.list_voices()

    assert [v.name for v in voices] == ["Alpha", "Zeta"]
    assert voices[0].language == "en"
    assert voices[1].language == "de"
    assert voices[1].gender == "female"


@pytest.mark.asyncio
@respx.mock
async def test_list_voices_caches_result() -> None:
    route = respx.get("https://api.elevenlabs.io/v1/voices").mock(
        return_value=httpx.Response(200, json={"voices": [{"voice_id": "1", "name": "A"}]})
    )

    backend = ElevenLabsBackend(_config())
    first = await backend.list_voices()
    second = await backend.list_voices()

    assert len(first) == 1
    assert len(second) == 1
    assert len(route.calls) == 1


@pytest.mark.asyncio
@respx.mock
async def test_list_voices_401_raises_authentication_error() -> None:
    respx.get("https://api.elevenlabs.io/v1/voices").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )

    backend = ElevenLabsBackend(_config())
    with pytest.raises(AuthenticationError):
        await backend.list_voices()


@pytest.mark.asyncio
@respx.mock
async def test_list_voices_invalid_json_raises_api_error() -> None:
    respx.get("https://api.elevenlabs.io/v1/voices").mock(
        return_value=httpx.Response(200, text="not-json")
    )

    backend = ElevenLabsBackend(_config())
    with pytest.raises(ElevenLabsAPIError):
        await backend.list_voices()


@pytest.mark.asyncio
async def test_synthesize_network_error_after_retries_exhausted() -> None:
    backend = ElevenLabsBackend(_config())

    with (
        patch.object(backend._client, "post", side_effect=httpx.ConnectError("conn-fail")),
        patch("app.backends.elevenlabs.random.uniform", return_value=0.0),
        patch("app.backends.elevenlabs.asyncio.sleep", new_callable=AsyncMock),
    ):
        with pytest.raises(NetworkError):
            await backend.synthesize(text="hello", voice_id="v1")
