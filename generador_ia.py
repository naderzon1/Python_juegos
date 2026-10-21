"""Lanzador del Estudio Generativo (texto, imagen y sonido con IA local).

En el teléfono (Pydroid 3, Pyto, a-Shell, Termux) o en el computador basta
con ejecutar este archivo: abre la interfaz en el navegador. No necesita
instalar nada: solo usa la biblioteca estándar de Python 3.9+.

También acepta los mismos argumentos que `python -m ia_generativa`:
    python generador_ia.py "bosque misterioso al amanecer"
"""

import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
if len(sys.argv) == 1:
    os.chdir(AQUI)  # al tocar "ejecutar", los resultados quedan en salida_ia/ junto a este archivo

from ia_generativa.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main(sys.argv[1:])
