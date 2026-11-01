"""Prueba de integración OPCIONAL con el servicio real de Edge TTS (requiere Internet).

No se ejecuta por defecto. Para activarla:
    $env:NADER_INTEGRATION = "1"; .\\.venv\\Scripts\\python.exe -m pytest -m integration
"""

import asyncio
import os

import pytest

from services.speech_service import EdgeSpeechService, available_edge_voices

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("NADER_INTEGRATION") != "1", reason="define NADER_INTEGRATION=1 para usar Internet"),
]


def test_edge_genera_mp3_real(tmp_path):
    destino = tmp_path / "prueba.mp3"
    asyncio.run(EdgeSpeechService().synthesize("Prueba de NADER AI.", "es-CO-SalomeNeural", 0, destino))
    datos = destino.read_bytes()
    assert len(datos) > 1000
    assert datos[:3] == b"ID3" or datos[0] == 0xFF


def test_voces_configuradas_existen_en_edge():
    disponibles = asyncio.run(available_edge_voices())
    assert disponibles is not None, "sin conexión con Edge"
    assert disponibles == {"es-CO-SalomeNeural", "es-CO-GonzaloNeural", "es-ES-ElviraNeural", "es-ES-AlvaroNeural"}
