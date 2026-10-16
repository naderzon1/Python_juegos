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
| **Turbo Ruta HD** | igual que Turbo Ruta; botón 🎥 o tecla C para cambiar la cámara | versión en 3D (three.js): 7 circuitos cerrados con desniveles, luces y sombras, autos 3D del garaje, rivales que frenan en las curvas y adelantan, minimapa, gráficos altos o rápidos, 2 jugadores |
| **Turbo Ruta** | botones de dirección, acelerar, freno y nitro | carreras de 4 vueltas en 7 pistas (Valle Verde, Desierto, Montaña, Ciudad, Playa, Otoño y Volcán) contra 10 rivales; garaje con 5 modelos de auto (cada uno maneja distinto) y 14 colores; 2 jugadores en pantalla dividida (en tablet, la mitad de arriba va girada para quien está enfrente) |

En el computador se juegan con el teclado (la ayuda aparece bajo cada juego), y en cualquier aparato
también con un mando Bluetooth o USB. El sitio se instala como app ("Agregar a pantalla de inicio") y,
después de abrirlo una vez con internet, funciona sin conexión (`docs/sw.js` guarda los archivos).
Con el teléfono vertical, Pong, Naves y Turbo Ruta reacomodan su cancha o su vista.
Todo el sonido se sintetiza en el navegador; no hay archivos de audio.
Los juegos 3D usan [three.js](https://threejs.org), que se carga desde internet al abrirlos.

**Emuladores de Nintendo 64 y Super Nintendo** (`docs/emulador.html?s=n64` y `?s=snes`): abren juegos que
elijas desde tu aparato (.z64, .n64, .v64, .sfc, .smc o dentro de un .zip). Usan [EmulatorJS](https://emulatorjs.org)
(código abierto, GPL-3.0) con los núcleos mupen64plus y snes9x, cargados desde su servidor.
Traen juegos caseros libres para abrir con un toque (`docs/juegos/`): en N64, Sblobber 64 (licencia MIT)
y Kumi-Daiko Beatoff 64 (dominio público); en Super Nintendo, Super Sudoku (licencia MIT). Créditos en
`docs/juegos/LICENCIAS.txt`. Para lo demás, usa copias
de tus cartuchos u otros juegos caseros libres.
El **modo mejorado** (panel en la pantalla de elegir juego, se recuerda por consola) agrega: en N64, imagen HD
(1280×960) o máxima (1920×1440) con suavizado de bordes, pantalla ancha 16:9 y texturas suavizadas (xBRZ);
en ambas consolas, filtros de televisor clásico, televisor curvo, monitor de arcade o suavizado HQ,
rebobinar (botón ⏪ mantenido o tecla Retroceso) y avance rápido ×2, ×3 o ×5 (botón ⏩ o tecla Tab).

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

## GALACTIC DOMINION 3D

[`galactic_dominion_3d/`](galactic_dominion_3d/) es un proyecto aparte, más grande: un arcade espacial 3D con
progresión RPG hecho con Panda3D. Tiene cinco galaxias, jefes con fases, ocho armas, taller de mejoras,
evolución de la nave (Mk I–V) y guardado de partidas. Usa su propio entorno virtual; en Windows basta con
ejecutar `galactic_dominion_3d\jugar.bat`. Las instrucciones completas están en su
[README](galactic_dominion_3d/README.md).
