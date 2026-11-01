"""Memoria opcional de conversaciones, separada de la lógica de generación.

- Desactivada por defecto (NullStore): no se guarda nada.
- Con NADER_MEMORY_ENABLED=true se usa JsonFileStore: un archivo JSON por conversación en
  data/conversaciones/. Se borra con DELETE /api/memory/{id} o eliminando la carpeta.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from pathlib import Path
from typing import Protocol

from .llm_service import ChatMessage

_ID_VALIDO = re.compile(r"^[a-f0-9]{32}$")
MAX_MESSAGES = 40  # se conservan los últimos mensajes para no crecer sin límite


class ConversationStore(Protocol):
    enabled: bool

    def new_id(self) -> str: ...
    def load(self, conversation_id: str) -> list[ChatMessage]: ...
    def save(self, conversation_id: str, history: list[ChatMessage]) -> None: ...
    def delete(self, conversation_id: str) -> bool: ...


class NullStore:
    enabled = False

    def new_id(self) -> str:
        return uuid.uuid4().hex

    def load(self, conversation_id: str) -> list[ChatMessage]:
        return []

    def save(self, conversation_id: str, history: list[ChatMessage]) -> None:
        return None

    def delete(self, conversation_id: str) -> bool:
        return False


class JsonFileStore:
    enabled = True

    def __init__(self, directory: Path):
        self.directory = directory
        self._lock = threading.Lock()

    def new_id(self) -> str:
        return uuid.uuid4().hex

    def _path(self, conversation_id: str) -> Path | None:
        # El id solo puede ser hexadecimal: impide rutas arbitrarias.
        if not _ID_VALIDO.match(conversation_id or ""):
            return None
        return self.directory / f"{conversation_id}.json"

    def load(self, conversation_id: str) -> list[ChatMessage]:
        ruta = self._path(conversation_id)
        if ruta is None or not ruta.is_file():
            return []
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return [ChatMessage(m["role"], m["content"]) for m in datos.get("messages", [])]

    def save(self, conversation_id: str, history: list[ChatMessage]) -> None:
        ruta = self._path(conversation_id)
        if ruta is None:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        datos = {"messages": [m.__dict__ for m in history[-MAX_MESSAGES:]]}
        with self._lock:
            ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")

    def delete(self, conversation_id: str) -> bool:
        ruta = self._path(conversation_id)
        if ruta is None or not ruta.is_file():
            return False
        ruta.unlink()
        return True


def build_store(enabled: bool, directory: Path) -> ConversationStore:
    return JsonFileStore(directory) if enabled else NullStore()
