"""Empaqueta el proyecto en un ZIP de entrega.

Excluye el entorno virtual, las cachés, las partidas y registros, el audio
generado (el juego lo vuelve a crear) y los ZIP anteriores.

    python tools/package.py              # crea ../galactic_dominion_3d.zip
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".venv", "__pycache__", ".pytest_cache", ".git"}
EXCLUDED_PATHS = {ROOT / "assets" / "audio" / "generated"}


def wanted(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return False
    if any(path == p or p in path.parents for p in EXCLUDED_PATHS):
        return False
    if rel.parts[0] == "saves" and path.name != ".gitkeep":
        return False
    return path.suffix not in (".zip", ".pyc")


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "galactic_dominion_3d.zip"
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and wanted(p))
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, Path("galactic_dominion_3d") / path.relative_to(ROOT))
    print(f"{target} ({len(files)} archivos, {target.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
