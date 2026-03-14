"""Azure Neural TTS backend stub.

See ARCHITECTURE.md §4.2. Full implementation deferred to Phase 2.
"""

from __future__ import annotations

from app.backends.base import TTSBackend, VoiceInfo
from app.config import AzureConfig


class AzureBackend(TTSBackend):
    """Stub for Azure Cognitive Services TTS backend (Phase 2).

    See ARCHITECTURE.md §4.2 for the planned implementation details:
    - Endpoint: Azure Cognitive Services Speech SDK
    - Voice: de-DE-KatjaNeural / de-DE-ConradNeural
    - Auth: Ocp-Apim-Subscription-Key header
    """

    def __init__(self, config: AzureConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "azure"

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_format: str = "mp3_44100_128",
    ) -> bytes:
        raise NotImplementedError("Azure backend not yet implemented (Phase 2)")

    async def list_voices(self) -> list[VoiceInfo]:
        raise NotImplementedError("Azure backend not yet implemented (Phase 2)")


def create_azure_backend(config: AzureConfig) -> AzureBackend:
    return AzureBackend(config)
