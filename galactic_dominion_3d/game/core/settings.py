"""Ajustes del jugador (gráficos, audio y controles).

Los valores por defecto salen de ``config/``; lo que el jugador cambia en el
menú de configuración se guarda en ``saves/settings.json`` y se superpone a
esos valores. Un archivo dañado no impide arrancar: se ignora y se informa.
"""
from __future__ import annotations

import copy
from pathlib import Path

from game.core.config import GameConfig
from game.persistence.files import atomic_write_json, read_json


class Settings:
    def __init__(self, config: GameConfig, path: Path):
        self.config = config
        self.path = Path(path)
        self.warning: str | None = None
        g, c, a = config.graphics, config.controls, config.audio
        self.data: dict = {
            "graphics_preset": g["preset"],
            "fullscreen": bool(g["window"]["fullscreen"]),
            "width": int(g["window"]["width"]),
            "height": int(g["window"]["height"]),
            "fps_target": int(g["fps_target"]),
            "vsync": bool(g.get("vsync", False)),
            "show_fps": bool(g.get("show_fps", False)),
            "fov": float(g.get("fov", 72)),
            "ui_scale": 1.0,  # tamaño de la interfaz (0.7 = pantallas pequeñas, 1.5 = televisores)
            "bloom": None,  # None = lo que diga el preajuste
            "mouse_sensitivity": float(c["mouse_sensitivity"]),
            "invert_y": bool(c["invert_y"]),
            "bindings": copy.deepcopy(c["bindings"]),
            "gamepad_enabled": bool(c["gamepad"]["enabled"]),
            "master": float(a["master"]),
            "music": float(a["music"]),
            "sfx": float(a["sfx"]),
        }
        self.load()

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def quality(self) -> dict:
        """Parámetros del preajuste gráfico activo, con las anulaciones del jugador."""
        preset = dict(self.config.graphics["presets"][self.data["graphics_preset"]])
        if self.data.get("bloom") is not None:
            preset["bloom"] = bool(self.data["bloom"])
        return preset

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            stored = read_json(self.path)
            if not isinstance(stored, dict):
                raise ValueError("formato inesperado")
        except (OSError, ValueError) as exc:
            self.warning = f"No se pudieron leer los ajustes guardados ({exc}); se usan los predeterminados."
            return
        for key, default in self.data.items():
            if key not in stored:
                continue
            value = stored[key]
            if key == "bindings":
                if isinstance(value, dict):
                    for action, keys in value.items():
                        if action in default and isinstance(keys, list) and all(isinstance(k, str) for k in keys):
                            default[action] = keys
                continue
            if key == "graphics_preset" and value not in self.config.graphics["presets"]:
                continue
            if key == "bloom":
                self.data[key] = None if value is None else bool(value)
                continue
            try:
                self.data[key] = type(default)(value) if default is not None else value
            except (TypeError, ValueError):
                continue
        for key in ("master", "music", "sfx"):
            self.data[key] = min(1.0, max(0.0, self.data[key]))
        self.data["mouse_sensitivity"] = min(4.0, max(0.1, self.data["mouse_sensitivity"]))
        self.data["fps_target"] = min(240, max(30, self.data["fps_target"]))
        self.data["ui_scale"] = min(1.5, max(0.7, self.data["ui_scale"]))
        self.data["width"] = min(7680, max(800, self.data["width"]))
        self.data["height"] = min(4320, max(600, self.data["height"]))

    def save(self) -> None:
        atomic_write_json(self.path, self.data, keep_backup=False)
