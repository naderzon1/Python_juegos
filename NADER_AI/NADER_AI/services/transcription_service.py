"""Reconocimiento de voz en el servidor (integración pendiente).

/api/transcribe ya recibe audio, pero responde 503 hasta configurar un proveedor.
Mientras tanto la interfaz ofrece dictado con el reconocimiento de voz del navegador
(Web Speech API), que funciona en Chrome y Edge y envía el audio al servicio de Google o
Microsoft según el navegador.
"""

from __future__ import annotations

from typing import Protocol

from .errors import NotConfigured


class TranscriptionProvider(Protocol):
    name: str
    configured: bool

    async def transcribe(self, audio: bytes, mime_type: str) -> str:
        ...


class NoTranscriptionProvider:
    name = "ninguno"
    configured = False

    async def transcribe(self, audio: bytes, mime_type: str) -> str:
        raise NotConfigured("No hay un proveedor de transcripción configurado (NADER_TRANSCRIPTION_PROVIDER).")


def build_transcription_provider(provider: str) -> TranscriptionProvider:
    return NoTranscriptionProvider()
