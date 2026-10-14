# Juegos en Python y en la web

Juegos clásicos hechos en Python para el computador, y versiones web de los juegos 2D
que funcionan en teléfonos y tablets con controles táctiles.

## Versiones web (teléfono, tablet y computador)

Están en la carpeta [`docs/`](docs/) y no necesitan instalar nada: se abren en el navegador.

| Juego | En pantalla táctil | Modos |
|---|---|---|
| **Bloques** | botones ◀ ▼ ▶, girar, soltar y guardar; tocar el tablero también gira | 1 jugador, con récord guardado |
| **Pong** | arrastrar el dedo arriba y abajo | contra el PC (3 dificultades) o 2 jugadores, cada uno en su mitad |
| **Duelo de naves** | arrastrar para mover; con el dedo apoyado dispara | tú vs PC, 2 en equipo vs PC, 1 vs 1 en la misma tablet |

En el computador se juegan con el teclado (la ayuda aparece bajo cada juego).
Todo el sonido se sintetiza en el navegador; no hay archivos de audio.

Para publicarlas con GitHub Pages: *Settings → Pages → Deploy from a branch → `main` / `/docs`*.

## Versiones de escritorio en Python

| Archivo | Juego | Requiere |
|---|---|---|
| `bloques.py` | Puzle de piezas que caen, con música | `pygame` |
| `pong.py` | Pong contra el computador | solo Python (tkinter) |
| `naves.py` | Duelo de naves 2D, 3 modos de juego | solo Python (tkinter) |
| `naves3d.py` | Duelo de naves en 3D, 3 modos de juego | `ursina` |
| `plataformas3d.py` | Aventura de plataformas 3D con sonido | `ursina` |
| `mnist.py` | Red neuronal que reconoce dígitos escritos a mano | `tensorflow` |
| `test_tensorflow.py` | Prueba de que TensorFlow quedó bien instalado | `tensorflow` |

Instalación (Python 3.13; TensorFlow aún no existe para 3.14):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install pygame ursina tensorflow matplotlib pillow
python bloques.py
```
