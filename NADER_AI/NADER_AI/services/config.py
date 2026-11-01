"""Configuración de NADER AI leída de variables de entorno (y de un archivo .env opcional)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
APP_NAME = "NADER AI"
APP_VERSION = "0.1.0"

# Modelo que se usa con cada proveedor si NADER_LLM_MODEL está vacío.
MODELO_POR_DEFECTO = {"anthropic": "claude-opus-5-5", "ollama": "llama3.2"}


def cargar_env(ruta: Path) -> None:
    """Lee un .env sencillo (CLAVE=valor) sin pisar variables ya definidas en el sistema."""
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave, valor = clave.strip(), valor.strip().strip('"').strip("'")
        if clave and valor and clave not in os.environ:
            os.environ[clave] = valor


def _int(nombre: str, defecto: int) -> int:
    try:
        return int(os.environ.get(nombre, defecto))
    except ValueError:
        return defecto


def _bool(nombre: str, defecto: bool = False) -> bool:
    return os.environ.get(nombre, str(defecto)).strip().lower() in {"1", "true", "si", "sí", "yes"}


@dataclass(frozen=True)
class Settings:
    max_text_length: int = 5000
    audio_dir: Path = RAIZ / "generated_audio"
    audio_max_age_seconds: int = 600
    tts_timeout_seconds: int = 60
    max_concurrent_tts: int = 3
    queue_wait_seconds: int = 10
    cors_origins: list[str] = field(default_factory=list)
    llm_provider: str = "ninguno"
    llm_model: str = "claude-opus-5-5"
    llm_max_input: int = 8000
    ollama_url: str = "http://127.0.0.1:11434"
    image_provider: str = "ninguno"
    transcription_provider: str = "ninguno"
    memory_enabled: bool = False
    memory_dir: Path = RAIZ / "data" / "conversaciones"

    @classmethod
    def from_env(cls) -> "Settings":
        cargar_env(RAIZ / ".env")
        proveedor = os.environ.get("NADER_LLM_PROVIDER", "ninguno").strip().lower()
        origenes = [o.strip() for o in os.environ.get("NADER_CORS_ORIGINS", "").split(",") if o.strip()]
        return cls(
            max_text_length=_int("NADER_MAX_TEXT_LENGTH", 5000),
            audio_max_age_seconds=_int("NADER_AUDIO_MAX_AGE_SECONDS", 600),
            tts_timeout_seconds=_int("NADER_TTS_TIMEOUT_SECONDS", 60),
            max_concurrent_tts=max(1, _int("NADER_MAX_CONCURRENT_TTS", 3)),
            queue_wait_seconds=_int("NADER_QUEUE_WAIT_SECONDS", 10),
            cors_origins=origenes,
            llm_provider=proveedor,
            llm_model=os.environ.get("NADER_LLM_MODEL", "").strip() or MODELO_POR_DEFECTO.get(proveedor, ""),
            llm_max_input=_int("NADER_LLM_MAX_INPUT", 8000),
            ollama_url=os.environ.get("NADER_OLLAMA_URL", "").strip() or "http://127.0.0.1:11434",
            image_provider=os.environ.get("NADER_IMAGE_PROVIDER", "ninguno").strip().lower(),
            transcription_provider=os.environ.get("NADER_TRANSCRIPTION_PROVIDER", "ninguno").strip().lower(),
            memory_enabled=_bool("NADER_MEMORY_ENABLED"),
        )
