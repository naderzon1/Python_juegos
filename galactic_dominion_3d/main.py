"""GALACTIC DOMINION 3D — punto de entrada.

    python main.py

Los registros se guardan en ``saves/game.log``.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.core.config import ConfigError  # noqa: E402
from game.core.paths import saves_dir  # noqa: E402


def setup_logging() -> None:
    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler(saves_dir() / "game.log", encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=handlers)


def main() -> int:
    setup_logging()
    log = logging.getLogger("galactic_dominion")
    try:
        from game.core.app import GameApp
        app = GameApp()
    except ConfigError as exc:
        log.error("%s", exc)
        print("\nNo se pudo iniciar GALACTIC DOMINION 3D por un error de configuración:\n", exc, file=sys.stderr)
        return 2
    log.info("GALACTIC DOMINION 3D iniciado")
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
