"""Amazon Polly TTS backend stub.

See ARCHITECTURE.md §4.3. Full implementation deferred to Phase 2.
"""

from __future__ import annotations

from app.backends.base import TTSBackend, VoiceInfo
from app.config import PollyConfig


class PollyBackend(TTSBackend):
    """Stub for Amazon Polly TTS backend (Phase 2).

    See ARCHITECTURE.md §4.3 for the planned implementation details:
    - AWS SDK: boto3 polly.synthesize_speech()
    - Voice: Vicki (de-DE), Daniel (de-DE), Neural engine
    - Output: mp3
    """

    def __init__(self, config: PollyConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "polly"

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_format: str = "mp3_44100_128",
    ) -> bytes:
        raise NotImplementedError("Polly backend not yet implemented")

    def list_voices(self) -> list[VoiceInfo]:
        raise NotImplementedError("Polly backend not yet implemented")


def create_polly_backend(config: PollyConfig) -> PollyBackend:
    return PollyBackend(config)
