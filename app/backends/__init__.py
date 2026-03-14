"""TTS backend package — exports all backend classes and the router factory."""

from app.backends.azure import AzureBackend
from app.backends.base import TTSBackend, VoiceInfo, get_backend
from app.backends.elevenlabs import ElevenLabsBackend
from app.backends.piper import PiperBackend
from app.backends.polly import PollyBackend
from app.backends.router import BackendRouter, BackendUnavailableError, InvalidBackendError

__all__ = [
    "TTSBackend",
    "VoiceInfo",
    "get_backend",
    "ElevenLabsBackend",
    "AzureBackend",
    "PollyBackend",
    "PiperBackend",
    "BackendRouter",
    "InvalidBackendError",
    "BackendUnavailableError",
]
