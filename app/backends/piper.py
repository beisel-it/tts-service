"""Piper self-hosted TTS backend stub.

See ARCHITECTURE.md §4.4. Full implementation deferred to Phase 2.
"""

from __future__ import annotations

from app.backends.base import TTSBackend, VoiceInfo
from app.config import PiperConfig


class PiperBackend(TTSBackend):
    """Stub for Piper self-hosted TTS backend (Phase 2).

    See ARCHITECTURE.md §4.4 for the planned implementation details:
    - Local subprocess or HTTP to local Piper service
    - Model: de_DE-thorsten-high
    - Output: WAV → convert to MP3 via ffmpeg
    """

    def __init__(self, config: PiperConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "piper"

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_format: str = "mp3_44100_128",
    ) -> bytes:
        raise NotImplementedError("Piper backend not yet implemented (Phase 2)")

    async def list_voices(self) -> list[VoiceInfo]:
        raise NotImplementedError("Piper backend not yet implemented (Phase 2)")


def create_piper_backend(config: PiperConfig) -> PiperBackend:
    return PiperBackend(config)
