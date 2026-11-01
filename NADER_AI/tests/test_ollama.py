"""Proveedor Ollama con un servidor simulado (httpx.MockTransport): no necesita Ollama instalado."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from services.config import Settings
from services.errors import ProviderError
from services.llm_service import ChatMessage, OllamaProvider, build_llm_provider


def proveedor(manejador) -> OllamaProvider:
    return OllamaProvider("llama3.2", "http://ollama.test/", transport=httpx.MockTransport(manejador))


def test_ollama_responde_y_envia_historial():
    recibido = {}

    def manejador(request: httpx.Request) -> httpx.Response:
        recibido["url"] = str(request.url)
        recibido["cuerpo"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": " Hola, soy NADER AI. "}})

    texto = asyncio.run(proveedor(manejador).reply([ChatMessage("user", "Hola")]))

    assert texto == "Hola, soy NADER AI."
    assert recibido["url"] == "http://ollama.test/api/chat"
    assert recibido["cuerpo"]["model"] == "llama3.2"
    assert recibido["cuerpo"]["stream"] is False
    assert recibido["cuerpo"]["messages"][0]["role"] == "system"
    assert recibido["cuerpo"]["messages"][1] == {"role": "user", "content": "Hola"}


def test_ollama_modelo_no_descargado():
    p = proveedor(lambda r: httpx.Response(404, json={"error": "model 'llama3.2' not found"}))
    with pytest.raises(ProviderError) as error:
        asyncio.run(p.reply([ChatMessage("user", "Hola")]))
    assert error.value.code == "modelo_no_encontrado"
    assert "ollama pull llama3.2" in error.value.message


def test_ollama_apagado():
    def manejador(request):
        raise httpx.ConnectError("conexión rechazada", request=request)

    with pytest.raises(ProviderError) as error:
        asyncio.run(proveedor(manejador).reply([ChatMessage("user", "Hola")]))
    assert "Ollama esté abierto" in error.value.message


def test_ollama_respuesta_vacia():
    p = proveedor(lambda r: httpx.Response(200, json={"message": {"content": "  "}}))
    with pytest.raises(ProviderError):
        asyncio.run(p.reply([ChatMessage("user", "Hola")]))


def test_build_y_modelo_por_defecto(monkeypatch):
    assert isinstance(build_llm_provider("ollama", "llama3.2"), OllamaProvider)
    monkeypatch.setenv("NADER_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("NADER_LLM_MODEL", raising=False)
    ajustes = Settings.from_env()
    assert ajustes.llm_model == "llama3.2"
    assert ajustes.ollama_url == "http://127.0.0.1:11434"
