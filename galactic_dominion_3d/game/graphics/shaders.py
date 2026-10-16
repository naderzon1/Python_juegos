"""Carga de shaders GLSL desde ``assets/shaders`` con caché y errores claros."""
from __future__ import annotations

from panda3d.core import Filename, Shader

from game.core.paths import SHADER_DIR, require_file

_CACHE: dict = {}


def load_shader(vertex: str, fragment: str) -> Shader:
    key = (vertex, fragment)
    if key not in _CACHE:
        vpath = require_file(SHADER_DIR / vertex)
        fpath = require_file(SHADER_DIR / fragment)
        shader = Shader.load(Shader.SL_GLSL,
                             vertex=Filename.fromOsSpecific(str(vpath)).getFullpath(),
                             fragment=Filename.fromOsSpecific(str(fpath)).getFullpath())
        if shader is None:
            raise RuntimeError(f"No se pudo compilar el shader {vertex} + {fragment}")
        _CACHE[key] = shader
    return _CACHE[key]
