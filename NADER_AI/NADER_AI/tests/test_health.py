"""Arranque del servidor, estado, documentación e interfaz."""

import re

from services.config import APP_VERSION, RAIZ


def test_servidor_inicia_y_health_responde(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    datos = res.json()
    assert datos["status"] == "ok"
    assert datos["app"] == "NADER AI"
    assert datos["version"] == APP_VERSION
    assert datos["limits"]["max_text_length"] == 5000


def test_health_identifica_modulos_completos_y_pendientes(client):
    modulos = client.get("/api/health").json()["modules"]
    assert modulos["voz_edge"] == {"estado": "completo", "requiere_internet": True}
    assert modulos["llm"]["estado"] == "no_configurado"
    assert modulos["imagenes"]["estado"] == "pendiente"
    assert modulos["transcripcion"]["estado"] == "pendiente"
    assert modulos["memoria"]["estado"] == "desactivada"


def test_documentacion_activa(client):
    assert client.get("/docs").status_code == 200
    rutas = client.get("/openapi.json").json()["paths"]
    for ruta in ("/api/health", "/api/voices", "/api/audio", "/api/chat"):
        assert ruta in rutas


def test_interfaz_se_sirve_con_sus_recursos(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "NADER AI" in res.text
    for recurso in re.findall(r'(?:href|src)="(/static/[^"]+)"', res.text):
        assert client.get(recurso).status_code == 200, recurso


def test_interfaz_usa_las_rutas_de_la_api(client):
    js = client.get("/static/app.js").text
    for ruta in ("/api/health", "/api/voices", "/api/audio", "/api/chat"):
        assert f'"{ruta}"' in js
    # toda ruta /api/ mencionada en la interfaz existe en el servidor
    rutas = client.get("/openapi.json").json()["paths"]
    for ruta in set(re.findall(r'"(/api/[a-z]+)"', js)):
        assert ruta in rutas, ruta


def test_no_expone_directorios_internos(client):
    assert client.get("/static/../server.py").status_code == 404
    assert client.get("/generated_audio/").status_code == 404
    assert client.get("/static/").status_code == 404


def test_sin_credenciales_en_el_proyecto():
    sospechosos = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{32,}")
    for archivo in RAIZ.rglob("*"):
        if ".venv" in archivo.parts or not archivo.is_file() or archivo.suffix not in {".py", ".js", ".html", ".md", ".example", ".txt", ".css"}:
            continue
        assert not sospechosos.search(archivo.read_text(encoding="utf-8", errors="ignore")), archivo
