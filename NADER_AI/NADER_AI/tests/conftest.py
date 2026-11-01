"""Fixtures comunes: la app se crea con un servicio de voz simulado y un directorio temporal."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import create_app
from services.config import Settings
from services.errors import ProviderError


def mp3_valido(frames: int = 4) -> bytes:
    """Bytes de un MP3 real: tramas MPEG-1 Layer III a 128 kbps / 44,1 kHz (417 bytes cada una)."""
    cabecera = bytes([0xFF, 0xFB, 0x90, 0x64])
    return (cabecera + bytes(417 - 4)) * frames


class FakeSpeech:
    """Imita a EdgeSpeechService sin conectarse a Internet."""

    def __init__(self, error: Exception | None = None, delay: float = 0.0):
        self.error = error
        self.delay = delay
        self.calls: list[dict] = []

    async def synthesize(self, text: str, voice: str, rate: int, destination: Path) -> None:
        self.calls.append({"text": text, "voice": voice, "rate": rate, "destination": destination})
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        destination.write_bytes(mp3_valido())


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return replace(Settings(), audio_dir=tmp_path / "audio", memory_dir=tmp_path / "memoria")


@pytest.fixture
def fake_speech() -> FakeSpeech:
    return FakeSpeech()


@pytest.fixture
def client(settings: Settings, fake_speech: FakeSpeech):
    app = create_app(settings, speech=fake_speech)
    with TestClient(app) as c:  # el bloque `with` ejecuta el arranque y el cierre (lifespan)
        yield c


@pytest.fixture
def make_client(settings: Settings):
    """Crea un cliente con un servicio de voz y ajustes a medida."""
    clientes: list[TestClient] = []

    def _make(speech=None, **cambios):
        app = create_app(replace(settings, **cambios), speech=speech or FakeSpeech())
        c = TestClient(app)
        c.__enter__()
        clientes.append(c)
        return c

    yield _make
    for c in clientes:
        c.__exit__(None, None, None)


__all__ = ["FakeSpeech", "ProviderError", "mp3_valido"]
