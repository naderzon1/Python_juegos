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
| **Naves 3D** | igual que el duelo de naves | los mismos tres modos, en 3D |
| **Plataformas 3D** | palanca en pantalla para moverse (a fondo corre) y botón para saltar | 1 jugador, con música |

En el computador se juegan con el teclado (la ayuda aparece bajo cada juego).
Todo el sonido se sintetiza en el navegador; no hay archivos de audio.
Los juegos 3D usan [three.js](https://threejs.org), que se carga desde internet al abrirlos.

**Emuladores de Nintendo 64 y Super Nintendo** (`docs/emulador.html?s=n64` y `?s=snes`): abren juegos que
elijas desde tu aparato (.z64, .n64, .v64, .sfc, .smc o dentro de un .zip). Usan [EmulatorJS](https://emulatorjs.org)
(código abierto, GPL-3.0) con los núcleos mupen64plus y snes9x, cargados desde su servidor.
No incluyen juegos: usa copias de tus cartuchos o homebrew libre.

Publicados en: https://naderzon1.github.io/Python_juegos/

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
