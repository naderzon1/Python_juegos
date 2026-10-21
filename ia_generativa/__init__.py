"""Estudio Generativo: IA generativa de texto, imagen y sonido en Python puro.

    from ia_generativa import generar
    r = generar("un mar en calma al atardecer")
    r["texto"]["cuerpo"], r["imagen"] (PNG en bytes), r["sonido"] (WAV en bytes)
"""

from .motor import generar, guardar
from .temas import interpretar

__all__ = ["generar", "guardar", "interpretar"]
__version__ = "1.0.0"
