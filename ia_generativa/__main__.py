"""Uso:

    python -m ia_generativa                      abre la interfaz web en el navegador
    python -m ia_generativa "mar en calma de noche"
    python -m ia_generativa "ciudad épica" --solo texto,imagen --semilla 7 --modo relato
    python -m ia_generativa --web --red          interfaz visible en tu red Wi-Fi
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .motor import TIPOS, generar, guardar


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="ia_generativa",
                                description="IA generativa de texto, imagen y sonido, 100 % local.")
    p.add_argument("prompt", nargs="*", help="descripción de lo que quieres crear")
    p.add_argument("--web", action="store_true", help="abre la interfaz web (por defecto sin prompt)")
    p.add_argument("--puerto", type=int, default=8000)
    p.add_argument("--red", action="store_true", help="permite abrirla desde otros aparatos de tu Wi-Fi")
    p.add_argument("--no-abrir", action="store_true", help="no abre el navegador automáticamente")
    p.add_argument("--solo", default=",".join(TIPOS), help="qué generar: texto,imagen,sonido")
    p.add_argument("--semilla", type=int, help="misma semilla = mismo resultado")
    p.add_argument("--modo", choices=("poema", "relato"), default="poema")
    p.add_argument("--ancho", type=int, default=512)
    p.add_argument("--alto", type=int, default=320)
    p.add_argument("--corpus", type=Path, help="archivo .txt propio para entrenar el modelo de texto")
    p.add_argument("--salida", type=Path, default=Path("salida_ia"), help="carpeta de resultados")
    a = p.parse_args(argv)

    if a.web or not a.prompt:
        from .servidor import iniciar
        iniciar(a.puerto, a.red, not a.no_abrir, a.salida.resolve())
        return

    tipos = [t.strip() for t in a.solo.split(",") if t.strip()]
    malos = [t for t in tipos if t not in TIPOS]
    if malos:
        p.error(f"tipo desconocido: {', '.join(malos)}")
    extra = a.corpus.read_text(encoding="utf-8") if a.corpus else ""
    prompt = " ".join(a.prompt)
    r = generar(prompt, tipos, a.semilla, a.modo, a.ancho, a.alto, extra)
    i = r["interpretacion"]
    print(f"\nEscena: {i['escena']} · Hora: {i['hora']} · Ánimo: {i['animo']} · Semilla: {i['semilla']}\n")
    if "texto" in r:
        print(f"  {r['texto']['titulo']}\n")
        print("\n".join("  " + linea for linea in r["texto"]["cuerpo"].splitlines()))
        print()
    for tipo, ruta in guardar(r, prompt, a.salida).items():
        print(f"  {tipo:7s} -> {ruta}  ({r['tiempos'][tipo]} s)")


if __name__ == "__main__":
    main(sys.argv[1:])
