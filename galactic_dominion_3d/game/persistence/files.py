"""Escritura segura de archivos JSON.

``atomic_write_json`` escribe primero en un archivo temporal de la misma
carpeta y luego lo reemplaza de forma atómica, así un cierre inesperado nunca
deja una partida a medio escribir. La versión anterior se conserva como
``.bak`` para poder recuperarla si el archivo nuevo se corrompe.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_json(path: Path, data: Any, keep_backup: bool = True) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.stem + "_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        if keep_backup and path.exists():
            shutil.copy2(path, backup_path(path))
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


def backup_path(path: Path) -> Path:
    return Path(path).with_suffix(Path(path).suffix + ".bak")


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
