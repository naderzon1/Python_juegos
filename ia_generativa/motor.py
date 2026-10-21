"""Punto de entrada común: un prompt -> texto, imagen y sonido coherentes."""

from __future__ import annotations

import re
import time
from pathlib import Path

from .imagen import generar_imagen
from .sonido import generar_sonido
from .temas import Interpretacion, interpretar, normalizar
from .texto import generar_texto

TIPOS = ("texto", "imagen", "sonido")


def generar(prompt: str, tipos=TIPOS, semilla: int | None = None, modo: str = "poema",
            ancho: int = 512, alto: int = 320, corpus_extra: str = "") -> dict:
    """Genera lo pedido. Imagen y sonido se devuelven como bytes (PNG y WAV)."""
    interp = interpretar(prompt, semilla)
    salida: dict = {"interpretacion": interp.describir(), "tiempos": {}}
    for tipo in tipos:
        inicio = time.perf_counter()
        salida[tipo] = generar_tipo(interp, tipo, modo, ancho, alto, corpus_extra)
        salida["tiempos"][tipo] = round(time.perf_counter() - inicio, 2)
    return salida


def generar_tipo(interp: Interpretacion, tipo: str, modo: str = "poema",
                 ancho: int = 512, alto: int = 320, corpus_extra: str = ""):
    if tipo == "texto":
        return generar_texto(interp, modo, corpus_extra)
    if tipo == "imagen":
        return generar_imagen(interp, ancho, alto)
    if tipo == "sonido":
        return generar_sonido(interp)
    raise ValueError(f"tipo desconocido: {tipo}")


def nombre_base(prompt: str, semilla: int) -> str:
    limpio = re.sub(r"[^a-z0-9]+", "-", normalizar(prompt).replace("ñ", "n"))[:40].strip("-") or "creacion"
    return f"{limpio}-{semilla}"


def guardar(resultado: dict, prompt: str, carpeta: Path) -> dict[str, Path]:
    """Guarda en disco lo generado y devuelve las rutas."""
    carpeta.mkdir(parents=True, exist_ok=True)
    base = nombre_base(prompt, resultado["interpretacion"]["semilla"])
    rutas = {}
    if "texto" in resultado:
        t = resultado["texto"]
        rutas["texto"] = carpeta / f"{base}.txt"
        rutas["texto"].write_text(f"{t['titulo']}\n\n{t['cuerpo']}\n", encoding="utf-8")
    if "imagen" in resultado:
        rutas["imagen"] = carpeta / f"{base}.png"
        rutas["imagen"].write_bytes(resultado["imagen"])
    if "sonido" in resultado:
        rutas["sonido"] = carpeta / f"{base}.wav"
        rutas["sonido"].write_bytes(resultado["sonido"])
    return rutas
