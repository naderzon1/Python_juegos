"""Rutas centralizadas del proyecto.

Todas las rutas se calculan a partir de la raíz del proyecto para que el juego
funcione sin importar el directorio desde el que se ejecute. La carpeta de
partidas guardadas se puede redirigir con la variable de entorno
``GD_SAVES_DIR`` (lo usan las pruebas automáticas para no tocar partidas reales).
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
ASSETS_DIR = ROOT / "assets"
SHADER_DIR = ASSETS_DIR / "shaders"
AUDIO_DIR = ASSETS_DIR / "audio"
GENERATED_AUDIO_DIR = AUDIO_DIR / "generated"
FONTS_DIR = ASSETS_DIR / "fonts"


def saves_dir() -> Path:
    custom = os.environ.get("GD_SAVES_DIR")
    path = Path(custom) if custom else ROOT / "saves"
    path.mkdir(parents=True, exist_ok=True)
    return path


def require_file(path: Path) -> Path:
    """Devuelve la ruta si existe; si no, lanza un error claro."""
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el recurso requerido: {path}")
    return path
