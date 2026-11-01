"""Conversación con un modelo de lenguaje.

La interfaz web solo conoce el endpoint /api/chat; el proveedor se elige con la variable
NADER_LLM_PROVIDER, así se puede cambiar de proveedor sin tocar la interfaz.

Estado:
- "ninguno" (por defecto): el endpoint responde 503 "no configurado". No se simulan respuestas.
- "anthropic": implementado con el SDK oficial de Claude. Necesita ANTHROPIC_API_KEY y el
  paquete `anthropic` (pip install anthropic). Se cobra en tu cuenta de la API de Claude.
- "ollama": modelo local servido por Ollama (https://ollama.com). Gratis y sin clave de API;
  necesita Ollama en marcha y el modelo descargado (ollama pull <modelo>).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Protocol

if __name__ == "__main__" and not __package__:
    # Ejecutado como archivo (python services/llm_service.py): se carga como parte del paquete
    # `services` para que funcionen los imports relativos.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "services"

from .errors import NotConfigured, ProviderError

log = logging.getLogger("nader.llm")


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


class LLMProvider(Protocol):
    name: str
    configured: bool

    async def reply(self, history: list[ChatMessage]) -> str:
        """Devuelve la respuesta del modelo al último mensaje de `history`."""


class NoLLMProvider:
    name = "ninguno"
    configured = False

    async def reply(self, history: list[ChatMessage]) -> str:
        del history  # sin proveedor no hay nada que responder
        raise NotConfigured(
            "No hay un modelo de lenguaje configurado. Define NADER_LLM_PROVIDER y su clave en el archivo .env."
        )


# Modelos que aceptan el respaldo automático del servidor ante un rechazo de seguridad.
_CON_RESPALDO = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

SYSTEM_PROMPT = (
    "Eres NADER AI, un asistente que responde en el idioma del usuario de forma clara y breve. "
    "Tus respuestas también pueden leerse en voz alta, así que evita tablas y formato complejo."
)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str):
        self.model = model
        self._client = None
        self.configured = False
        if not os.environ.get("ANTHROPIC_API_KEY"):
            log.warning("NADER_LLM_PROVIDER=anthropic pero falta ANTHROPIC_API_KEY")
            return
        try:
            import anthropic
        except ImportError:
            log.warning("NADER_LLM_PROVIDER=anthropic pero el paquete 'anthropic' no está instalado")
            return
        self._anthropic = anthropic
        self._client = anthropic.AsyncAnthropic()
        self.configured = True

    async def reply(self, history: list[ChatMessage]) -> str:
        if not self.configured:
            raise NotConfigured("El proveedor Anthropic necesita ANTHROPIC_API_KEY y el paquete 'anthropic'.")
        anthropic = self._anthropic
        params: dict = {
            "model": self.model,
            "max_tokens": 16000,
            "system": SYSTEM_PROMPT,
            "output_config": {"effort": "medium"},
            "messages": [{"role": m.role, "content": m.content} for m in history],
        }
        if self.model in _CON_RESPALDO:
            params["betas"] = ["server-side-fallback-2026-07-01"]
            params["fallbacks"] = "default"
        try:
            respuesta = await self._client.beta.messages.create(**params)
        except anthropic.AuthenticationError as error:
            raise ProviderError("La clave de API de Claude no es válida.", status_code=502) from error
        except anthropic.RateLimitError as error:
            raise ProviderError("Se alcanzó el límite de uso de la API. Espera un momento.", code="limite_uso") from error
        except anthropic.APIStatusError as error:
            raise ProviderError(f"El modelo de lenguaje devolvió un error ({error.status_code}).") from error
        except anthropic.APIConnectionError as error:
            raise ProviderError("No se pudo conectar con la API de Claude.") from error

        if respuesta.stop_reason == "refusal":
            raise ProviderError("El modelo no respondió a esta instrucción. Prueba a reformularla.", code="rechazado")
        texto = "".join(b.text for b in respuesta.content if b.type == "text").strip()
        if not texto:
            raise ProviderError("El modelo no devolvió texto.")
        return texto


class OllamaProvider:
    name = "ollama"
    configured = True  # no hay clave que comprobar; si Ollama no está abierto, falla al preguntar

    def __init__(self, model: str, base_url: str, timeout: float = 120.0, transport=None):
        import httpx

        self.model = model
        self.base_url = base_url.rstrip("/")
        self._httpx = httpx
        self._timeout = timeout
        self._transport = transport  # solo para pruebas (httpx.MockTransport)

    async def reply(self, history: list[ChatMessage]) -> str:
        httpx = self._httpx
        cuerpo = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}]
            + [{"role": m.role, "content": m.content} for m in history],
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as cliente:
                res = await cliente.post(f"{self.base_url}/api/chat", json=cuerpo)
        except httpx.ConnectError as error:
            raise ProviderError(
                f"No se pudo conectar con Ollama en {self.base_url}. Comprueba que Ollama esté abierto."
            ) from error
        except httpx.TimeoutException as error:
            raise ProviderError("Ollama tardó demasiado en responder.", code="tiempo_agotado", status_code=504) from error
        except httpx.HTTPError as error:
            raise ProviderError("Falló la conexión con Ollama.") from error

        if res.status_code == 404:
            raise ProviderError(
                f"Ollama no tiene el modelo '{self.model}'. Descárgalo con: ollama pull {self.model}",
                code="modelo_no_encontrado",
            )
        if res.status_code != 200:
            raise ProviderError(f"Ollama devolvió un error ({res.status_code}).")
        try:
            texto = (res.json().get("message") or {}).get("content", "").strip()
        except ValueError as error:
            raise ProviderError("Ollama devolvió una respuesta no válida.") from error
        if not texto:
            raise ProviderError("El modelo no devolvió texto.")
        return texto


def build_llm_provider(provider: str, model: str, ollama_url: str = "http://127.0.0.1:11434") -> LLMProvider:
    if provider == "anthropic":
        return AnthropicProvider(model)
    if provider == "ollama":
        return OllamaProvider(model, ollama_url)
    if provider not in ("", "ninguno", "none"):
        log.warning("Proveedor de LLM desconocido: %s (se usa 'ninguno')", provider)
    return NoLLMProvider()


if __name__ == "__main__":
    # Prueba rápida del proveedor configurado en .env:
    #   python services/llm_service.py "¿Quién eres?"
    import asyncio
    import sys

    from .config import Settings
    from .errors import AppError

    ajustes = Settings.from_env()
    llm = build_llm_provider(ajustes.llm_provider, ajustes.llm_model, ajustes.ollama_url)
    pregunta = " ".join(sys.argv[1:]) or "Hola, preséntate en una frase."
    print(f"Proveedor: {llm.name} | modelo: {ajustes.llm_model or '-'}")
    try:
        print(asyncio.run(llm.reply([ChatMessage("user", pregunta)])))
    except AppError as error:
        sys.exit(f"Error: {error.message}")
