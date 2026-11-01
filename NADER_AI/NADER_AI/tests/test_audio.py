"""Voces, validaciones y generación de audio (con el servicio de voz simulado)."""

import os
import re
import time

from tests.conftest import FakeSpeech, ProviderError, mp3_valido

from services.speech_service import VOICE_IDS, cleanup_old_audio, rate_to_edge


def pedir(client, **cuerpo):
    datos = {"text": "Bienvenido a NADER AI.", "voice": "es-CO-SalomeNeural", "rate": 0}
    datos.update(cuerpo)
    return client.post("/api/audio", json=datos)


# ---------- /api/voices ----------
def test_voices_estructura(client):
    res = client.get("/api/voices")
    assert res.status_code == 200
    datos = res.json()
    assert datos["default"] == "es-CO-SalomeNeural"
    ids = [v["id"] for v in datos["voices"]]
    assert ids == ["es-CO-SalomeNeural", "es-CO-GonzaloNeural", "es-ES-ElviraNeural", "es-ES-AlvaroNeural"]
    for voz in datos["voices"]:
        assert set(voz) >= {"id", "name", "locale", "gender"}
        assert voz["name"]


# ---------- Validaciones ----------
def test_texto_vacio_se_rechaza(client, fake_speech):
    for texto in ("", "   \n  "):
        res = pedir(client, text=texto)
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "texto_vacio"
        assert "vacío" in res.json()["error"]["message"]
    assert fake_speech.calls == []


def test_texto_ausente_se_rechaza(client):
    res = client.post("/api/audio", json={"voice": "es-CO-SalomeNeural"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "texto_vacio"


def test_texto_demasiado_largo_se_rechaza(client):
    res = pedir(client, text="a" * 5001)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "texto_demasiado_largo"


def test_longitud_maxima_configurable(make_client):
    c = make_client(max_text_length=10)
    assert pedir(c, text="12345678901").status_code == 422
    assert pedir(c, text="1234567890").status_code == 200


def test_voz_no_permitida_se_rechaza(client, fake_speech):
    res = pedir(client, voice="en-US-GuyNeural")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "voz_no_disponible"
    assert fake_speech.calls == []


def test_velocidad_fuera_de_rango_se_rechaza(client):
    for rate in (51, -51, 500):
        res = pedir(client, rate=rate)
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "velocidad_fuera_de_rango"
    assert pedir(client, rate="rápido").status_code == 422


def test_velocidad_en_los_limites_se_acepta(client, fake_speech):
    assert pedir(client, rate=-50).status_code == 200
    assert pedir(client, rate=50).status_code == 200
    assert [c["rate"] for c in fake_speech.calls] == [-50, 50]


def test_campos_desconocidos_y_json_invalido(client):
    assert pedir(client, extra=1).json()["error"]["code"] == "campo_desconocido"
    res = client.post("/api/audio", content=b"{no es json", headers={"Content-Type": "application/json"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "solicitud_invalida"


# ---------- Generación ----------
def test_generacion_simulada_devuelve_mp3_valido(client, fake_speech, settings):
    res = pedir(client, text="  Hola, mundo.  ", rate=10)
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mpeg"
    assert res.content == mp3_valido()
    assert res.content[:2] == b"\xff\xfb"  # sincronía de trama MPEG
    llamada = fake_speech.calls[0]
    assert llamada["text"] == "Hola, mundo."  # se recorta el espacio sobrante
    assert llamada["voice"] == "es-CO-SalomeNeural"
    assert llamada["rate"] == 10


def test_nombres_aleatorios_y_archivo_borrado_tras_enviar(client, fake_speech, settings):
    pedir(client)
    pedir(client)
    nombres = [c["destination"].name for c in fake_speech.calls]
    assert all(re.fullmatch(r"[0-9a-f]{32}\.mp3", n) for n in nombres)
    assert nombres[0] != nombres[1]
    assert all(c["destination"].parent == settings.audio_dir for c in fake_speech.calls)
    assert list(settings.audio_dir.glob("*.mp3")) == []  # se borran después de entregarse


def test_error_del_proveedor_se_gestiona(make_client, settings):
    speech = FakeSpeech(error=ProviderError("No se pudo conectar con el servicio de voz de Edge."))
    c = make_client(speech=speech)
    res = pedir(c)
    assert res.status_code == 502
    error = res.json()["error"]
    assert error["code"] == "error_proveedor"
    assert "servicio de voz" in error["message"]
    assert "Traceback" not in res.text
    assert list(settings.audio_dir.glob("*.mp3")) == []


def test_error_inesperado_no_expone_trazas(settings):
    from fastapi.testclient import TestClient

    from server import create_app

    app = create_app(settings, speech=FakeSpeech(error=RuntimeError("detalle interno secreto")))
    with TestClient(app, raise_server_exceptions=False) as c:
        res = pedir(c)
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "error_interno"
    assert "secreto" not in res.text and "Traceback" not in res.text


def test_tiempo_agotado(make_client):
    c = make_client(speech=FakeSpeech(delay=5), tts_timeout_seconds=1)
    res = pedir(c)
    assert res.status_code == 504
    assert res.json()["error"]["code"] == "tiempo_agotado"


# ---------- Utilidades del servicio de voz ----------
def test_rate_a_formato_edge():
    assert rate_to_edge(0) == "+0%"
    assert rate_to_edge(25) == "+25%"
    assert rate_to_edge(-50) == "-50%"


def test_limpieza_de_audios_antiguos(tmp_path):
    viejo, nuevo = tmp_path / "viejo.mp3", tmp_path / "nuevo.mp3"
    viejo.write_bytes(b"x")
    nuevo.write_bytes(b"x")
    hace_una_hora = time.time() - 3600
    os.utime(viejo, (hace_una_hora, hace_una_hora))
    assert cleanup_old_audio(tmp_path, max_age_seconds=600) == 1
    assert not viejo.exists() and nuevo.exists()


def test_voces_configuradas_solicitadas():
    assert VOICE_IDS == {"es-CO-SalomeNeural", "es-CO-GonzaloNeural", "es-ES-ElviraNeural", "es-ES-AlvaroNeural"}


# ---------- Módulos preparados (sin respuestas simuladas) ----------
def test_chat_sin_proveedor_responde_no_configurado(client):
    res = client.post("/api/chat", json={"message": "Hola"})
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "no_configurado"


def test_imagenes_y_transcripcion_pendientes(client):
    assert client.post("/api/images", json={"prompt": "un faro"}).status_code == 503
    res = client.post("/api/transcribe", content=b"\x00\x01", headers={"Content-Type": "audio/webm"})
    assert res.status_code == 503
    assert client.post("/api/transcribe", content=b"x", headers={"Content-Type": "text/plain"}).status_code == 415
