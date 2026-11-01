"""Síntesis de voz con Edge TTS (servicio externo de Microsoft: requiere conexión a Internet).

El servidor no genera la voz localmente: envía el texto al servicio de Edge y guarda el MP3
que devuelve. Los archivos se crean con nombres aleatorios y se borran al entregarse o al
superar la antigüedad configurada.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .errors import ProviderError

log = logging.getLogger("nader.voz")


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    locale: str
    gender: str


# Voces permitidas. Solo estas se aceptan en /api/audio.
VOICES: tuple[Voice, ...] = (
    Voice("es-CO-SalomeNeural", "Salomé · Colombia", "es-CO", "Femenina"),
    Voice("es-CO-GonzaloNeural", "Gonzalo · Colombia", "es-CO", "Masculina"),
    Voice("es-ES-ElviraNeural", "Elvira · España", "es-ES", "Femenina"),
    Voice("es-ES-AlvaroNeural", "Álvaro · España", "es-ES", "Masculina"),
)
VOICE_IDS = frozenset(v.id for v in VOICES)
DEFAULT_VOICE = VOICES[0].id


def rate_to_edge(rate: int) -> str:
    """Convierte la velocidad -50..+50 al formato de Edge TTS ("+10%", "-25%")."""
    return f"{rate:+d}%"


class SpeechService(Protocol):
    async def synthesize(self, text: str, voice: str, rate: int, destination: Path) -> None:
        """Genera un MP3 con el texto en `destination`. Lanza ProviderError si falla."""


class EdgeSpeechService:
    """Implementación con la biblioteca edge-tts."""

    async def synthesize(self, text: str, voice: str, rate: int, destination: Path) -> None:
        import edge_tts  # importación diferida: las pruebas no necesitan la red

        try:
            comunicador = edge_tts.Communicate(text, voice, rate=rate_to_edge(rate))
            await comunicador.save(str(destination))
        except edge_tts.exceptions.NoAudioReceived as error:
            raise ProviderError("El servicio de voz no devolvió audio. Prueba con otro texto o voz.") from error
        except (edge_tts.exceptions.EdgeTTSException, OSError) as error:
            # aiohttp.ClientError hereda de OSError en conexiones fallidas
            raise ProviderError("No se pudo conectar con el servicio de voz de Edge. Revisa tu conexión a Internet.") from error
        except Exception as error:  # errores inesperados de la biblioteca o del protocolo
            if error.__class__.__module__.startswith("aiohttp"):
                raise ProviderError("No se pudo conectar con el servicio de voz de Edge. Revisa tu conexión a Internet.") from error
            raise

        if not destination.is_file() or destination.stat().st_size == 0:
            raise ProviderError("El servicio de voz devolvió un archivo vacío.")


async def available_edge_voices(timeout: float = 10.0) -> set[str] | None:
    """Consulta qué voces configuradas existen hoy en Edge. Devuelve None si no hay conexión."""
    import asyncio

    import edge_tts

    try:
        voces = await asyncio.wait_for(edge_tts.list_voices(), timeout)
    except Exception as error:  # sin red, el servicio sigue usando la lista configurada
        log.warning("No se pudo verificar la lista de voces de Edge: %s", error.__class__.__name__)
        return None
    return {v["ShortName"] for v in voces} & VOICE_IDS


def new_audio_path(directory: Path) -> Path:
    """Ruta con nombre aleatorio e impredecible dentro del directorio de audio."""
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{uuid.uuid4().hex}.mp3"


def remove_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        log.warning("No se pudo borrar %s: %s", path.name, error)


def cleanup_old_audio(directory: Path, max_age_seconds: int) -> int:
    """Borra los MP3 más antiguos que `max_age_seconds`. Devuelve cuántos borró."""
    if not directory.is_dir():
        return 0
    limite = time.time() - max_age_seconds
    borrados = 0
    for archivo in directory.glob("*.mp3"):
        try:
            if archivo.stat().st_mtime < limite:
                archivo.unlink()
                borrados += 1
        except OSError:
            continue
    if borrados:
        log.info("Limpieza: %d archivos de audio antiguos eliminados", borrados)
    return borrados
