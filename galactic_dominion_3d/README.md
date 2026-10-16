# GALACTIC DOMINION 3D

Videojuego arcade espacial 3D con progresión RPG, escrito en Python sobre **Panda3D**.

Pilotas un caza a través de cinco galaxias dominadas por facciones hostiles: destruyes flotas, defiendes
estaciones, escoltas convoyes, recuperas materiales y derrotas jefes de varias fases. Con los créditos,
materiales, planos y componentes que consigues mejoras la nave, desbloqueas armas y naves nuevas y saltas a
galaxias más peligrosas. El progreso se guarda automáticamente.

- Interfaz en español; código e identificadores en inglés técnico, documentación en español.
- Plataforma probada: Windows 11 de 64 bits.
- Todo el contenido audiovisual (modelos, texturas, sonido y música) se genera con el código del propio
  proyecto. No hay recursos de terceros (ver `assets/LICENSES.md`).

---

## 1. Instalación

### Requisitos
- Python 3.11, 3.12 o 3.13 de 64 bits (probado con **3.13.13**). Panda3D 1.10.16 también publica versiones
  para 3.8–3.14.
- Tarjeta gráfica con OpenGL 3.2 o superior (necesario para los shaders GLSL).
- No hace falta conexión a Internet para jugar.

### Windows
```bat
cd galactic_dominion_3d
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```
Si tienes Python 3.11, cambia `-3.13` por `-3.11`. Si usas `uv`: `uv venv --python 3.13 .venv`.

### Linux y macOS
```bash
cd galactic_dominion_3d
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```
En Linux puede hacer falta instalar las bibliotecas de OpenGL y OpenAL del sistema
(por ejemplo `sudo apt install libgl1 libopenal1`).

## 2. Ejecución
```bash
python main.py
```
La primera vez el juego genera sus sonidos y su música (unos 3 segundos) en `assets/audio/generated/`.
Los registros se guardan en `saves/game.log`.

## 3. Controles

| Acción | Teclado y ratón | Mando (opcional) |
|---|---|---|
| Apuntar / girar la nave | Ratón | Stick izquierdo |
| Acelerar / frenar (acelerador persistente) | W / S | Stick derecho (vertical) |
| Desplazamiento lateral | A / D | Stick derecho (horizontal) |
| Alabeo (girar sobre el eje) | Q / E | LB / RB |
| Impulso (gasta energía) | Shift | A |
| Maniobra evasiva (invulnerable un instante, rompe el guiado de misiles) | Espacio | B |
| Disparo principal | Clic izquierdo | Gatillo derecho |
| Arma secundaria (misiles guiados o drones) | Clic derecho | Gatillo izquierdo |
| Arma especial (pulso de área o torpedo nova) | F | X |
| Siguiente objetivo / objetivo más cercano | Tab / T | Y |
| Cambiar arma principal | R | Cruceta arriba |
| Pausa | Esc | Start |
| Estadísticas de rendimiento (FPS) | F3 | — |

Las teclas se pueden reasignar en **Configuración → Asignación de teclas** (o en `config/controls.json`).
La sensibilidad del ratón y la inversión del eje Y también son ajustables.

Para lanzar misiles guiados, fija un objetivo (Tab) y mantenlo dentro de la mira hasta que el anillo rojo se
cierre («BLOQUEADO»). Sin bloqueo, los misiles salen en línea recta.

## 4. Cómo se juega

**Campaña.** Cinco galaxias en orden. En cada una hay misiones principales y secundarias; para saltar a la
siguiente galaxia hay que completar todas las principales, incluido el jefe.

| Galaxia | Identidad |
|---|---|
| 1. Frontera de Orión | Tutorial integrado, exploradores y patrullas, abre el taller de la estación Orión-7, primer jefe |
| 2. Nebulosa Carmesí | Niebla que reduce la visibilidad, campos de energía que drenan escudos, asteroides que dañan al chocar, interceptores rápidos con misiles y ataques coordinados |
| 3. Imperio de Hierro | Cañoneras con escudos fuertes, estaciones militares con torretas, escolta de convoy |
| 4. Abismo de los Antiguos | Enjambres alienígenas, leviatanes de élite, anomalías de radiación que se desplazan |
| 5. Núcleo del Vacío | Espectros de élite, grietas gravitatorias que atraen las naves, el Soberano del Vacío (4 fases) y el final |

**Tipos de misión:** destruir objetivos, destruir una flota completa, defender una estación, escoltar un
carguero, recuperar contenedores, sobrevivir un tiempo, eliminar una nave de élite y derrotar al jefe.
Al terminar se muestra un resumen con la experiencia, los créditos, los materiales, los planos y los objetos.
Si fracasas conservas la mitad de lo ganado en combate. Repetir una misión ya completada da el 40% de su
recompensa y no vuelve a dar planos.

**Jefes.** Cada jefe tiene modelo y escala propios, barra de vida, fases que cambian sus patrones de ataque
(abanicos de proyectiles, anillos, salvas de misiles, un rayo que avisa antes de disparar y refuerzos) y
**generadores** que hacen de puntos débiles: mientras quedan en pie, el núcleo recibe solo una parte del daño.
Para alcanzarlos conviene flanquear al jefe.

**Progresión.**
- Nivel del piloto: cada nivel suma un 1,5% de daño, escudo y casco.
- **Evolución automática de la nave** (según el nivel del piloto, sin comprar nada):

  | Etapa | Nivel | Qué cambia |
  |---|---|---|
  | Mk I | 1 | Configuración de fábrica |
  | Mk II | 4 | Placas de blindaje y franja de energía dorsal |
  | Mk III | 8 | Cañones gemelos (cada disparo sale por pares) y aletas ampliadas |
  | Mk IV | 12 | Alerones, alas extendidas y toberas auxiliares |
  | Mk V | 16 | Ráfagas triples, remates dorados y cresta dorsal |

  Cada etapa suma un 10% de casco y escudo y un 7% de daño. Los disparos son más grandes y brillantes, y el
  sonido de las armas y del motor se vuelve más grave y potente, con una capa extra de impacto desde Mk III.
  El modelo 3D gana piezas visibles. Al subir de etapa, el resumen de la misión lo anuncia; el hangar muestra la
  etapa actual y en qué nivel llega la siguiente. Todo se ajusta en `config/economy.json → ship_evolution`.
- Créditos y cinco materiales (uno por galaxia).
- Taller: 11 mejoras (potencia de fuego, velocidad, aceleración, maniobrabilidad, escudos, casco, energía,
  capacidad de misiles, sistemas de apuntado, motores y drones). Cada nivel cambia las estadísticas reales de
  la nave, y el panel del hangar las muestra al momento. Los niveles altos exigen tecnología de galaxias
  posteriores.
- Armería: 8 armas (cañón de energía, láser de precisión, cañón de plasma, cañón de dispersión, misiles
  guiados, drones de combate, pulso de área y torpedo nova). Las avanzadas necesitan su plano, que dan las
  misiones y los jefes.
- Astillero: 3 naves (Vanguard, Raptor y Bastion).
- Inventario: componentes de rareza común, poco común, rara, épica o legendaria. Se equipan en ranuras y se
  pueden vender.

## 5. Gráficos y rendimiento

Hay tres preajustes de calidad (Bajo, Medio y Alto), elegibles en Configuración y definidos en
`config/graphics.json`. Lo que está implementado de verdad:

- Escena HDR en búfer de coma flotante, **bloom** en dos escalas, mapeo de tonos filmico (aproximación ACES) y
  viñeta, con shaders GLSL propios (`assets/shaders/`).
- Antialiasing MSAA (2x/4x), sombras de la luz principal (preajuste Alto) e iluminación por píxel con
  materiales especulares.
- Estrellas en tres capas de profundidad, nebulosas por capas de sprites translúcidos, polvo espacial que da
  sensación de velocidad, planetas con texturas procedurales, atmósfera con efecto fresnel, anillos y lunas.
- Asteroides, restos de naves, estaciones, portal de salto animado y efecto de salto hiperespacial.
- Partículas reutilizables para motores, disparos, impactos, explosiones, humo, ondas de choque y restos;
  escudos visibles con destello en el punto de impacto; daño visible (humo y destellos) y viñeta roja al
  recibir daño en el casco; cámara con retardo, campo de visión dinámico y vibración moderada.

**No** hay trazado de rayos, iluminación global, desenfoque de movimiento, escalado de resolución, mapas de
normales ni materiales PBR.

Rendimiento medido en el equipo de desarrollo (calidad Alta, 1280×720, con la herramienta de prueba
automática): entre 50 y 57 FPS de media. Pulsa F3 en partida para ver los FPS, el tiempo por fotograma, las
entidades, los proyectiles y las partículas. Si tu equipo va justo, usa el preajuste Medio o Bajo (menos
estrellas, partículas, enemigos simultáneos y texturas más pequeñas) o baja el objetivo de FPS a 30.

## 6. Guardado

- Hay tres ranuras en `saves/slot_N.json`. Se guarda automáticamente al terminar cada misión, tras cada
  compra y al salir; también hay un botón «Guardar» en el mapa galáctico.
- La escritura es atómica: un cierre inesperado no deja la partida a medias. La versión anterior queda como
  `slot_N.json.bak`.
- Al cargar se validan los datos (tipos, rangos y referencias a armas, naves y misiones que existan). Si el
  archivo está dañado se recupera la copia `.bak`; si tampoco sirve, se aparta como `.corrupt-<fecha>` y el
  juego arranca igualmente.
- Sobrescribir una ranura ocupada pide confirmación.
- La configuración del jugador (gráficos, audio y controles) se guarda en `saves/settings.json`.

## 7. Arquitectura

```
galactic_dominion_3d/
├── main.py                  punto de entrada y registro (saves/game.log)
├── config/                  todos los datos de diseño en JSON
│   ├── weapons.json         armas del jugador y de los enemigos
│   ├── enemies.json         enemigos, élites y jefes (fases, generadores, recompensas)
│   ├── galaxies.json        galaxias: ambientación, peligros, misiones y oleadas
│   ├── ships.json           naves del jugador
│   ├── upgrades.json        mejoras del taller, costes y requisitos tecnológicos
│   ├── economy.json         inicio, materiales, nivel del piloto, rarezas, componentes y botín
│   ├── graphics.json · controls.json · audio.json
├── game/
│   ├── core/                app (estados y transiciones), flight (sesión de combate), config, settings,
│   │                        paths, camera_rig
│   ├── player/              player_ship (vuelo, armas, fijación, drones), controller (teclado, ratón, mando)
│   ├── ships/               entity (daño, escudos visibles), stats (estadísticas finales), allies
│   ├── combat/              damage (escudo/casco/críticos), world (reglas de daño), projectiles
│   ├── weapons/             weapon (definición, cadencia, munición)
│   ├── enemies/             enemy (naves y torretas), boss (fases, generadores, patrones)
│   ├── ai/                  fsm (máquina de estados y coordinación de escuadrones)
│   ├── galaxies/            scene (construcción del escenario por pasos), hazards (peligros)
│   ├── missions/            mission (objetivos, oleadas, recompensas), tutorial
│   ├── progression/         profile (perfil persistente), leveling (experiencia)
│   ├── inventory/           items (componentes y rareza)
│   ├── economy/             shop (taller, armería, astillero)
│   ├── audio/               synth (síntesis de sonido y música), manager (voces, espacial, música)
│   ├── graphics/            procedural, models, textures, effects, postfx, shaders, overlay
│   ├── ui/                  theme, hud, menus
│   └── persistence/         save_manager (validación y recuperación), files (escritura atómica)
├── assets/                  shaders GLSL, audio generado, LICENSES.md
├── saves/                   partidas, ajustes y registro (no se suben al repositorio)
├── tests/                   pruebas unitarias (pytest)
└── tools/                   smoke_test.py (prueba del juego real), model_viewer.py (visor de modelos)
```

**Separación motor/lógica.** La economía, la progresión, el daño, las armas, las misiones, la IA y el
guardado no dependen de la ventana, así que se prueban con pytest. El resto de módulos se apoya en Panda3D.

**Flujo de una misión.** `GameApp.start_mission` crea una `FlightSession`, cuyo escenario se construye por
pasos (uno por fotograma, detrás del efecto de salto, sin congelar la ventana). Al terminar, la sesión llama a
`GameApp.on_mission_end`, que aplica las recompensas, desbloquea la siguiente galaxia, guarda y muestra el
resumen. La sesión libera todos sus nodos, luces, niebla y tareas al cerrarse.

## 8. Cómo ampliar el juego

### Añadir una galaxia
Añade un objeto a `config/galaxies.json` y no hace falta tocar el código. Campos:
- `id`, `name`, `tier` (nivel tecnológico), `description`, `material` (uno de `economy.json`), `music`
  (una pista de `game/audio/synth.py`) y `arena_radius`.
- `difficulty`: multiplicadores `hp_mult`, `damage_mult` y `reward_mult`.
- `environment`: colores del fondo, nebulosas y estrellas, `sun`, `ambient`, `fog` (o `null`), `planets`
  (`kind`: `rocky`, `gas`, `ice` o `lava`; radio, distancia, ángulos, paleta, atmósfera, anillos y lunas),
  `asteroids` (`decor` y `hazard`), `debris`, `station` y `hazards` (`energy_field`, `anomaly`,
  `gravity_rift`).
- `enemy_pool` y `missions`.

La galaxia necesita al menos una misión principal de tipo `boss`. Al cargar, el juego valida todas las
referencias y avisa con un mensaje claro si algo no existe.

### Añadir una misión
Dentro de `missions`: `id`, `name`, `type` (uno de los ocho tipos), `main`, `requires` (misiones previas),
`params` (por ejemplo `count`, `duration`, `station_hull`, `distance`, `enemy` o `boss`), `waves`
(`delay`, `enemies`, `elite`), `reinforce_at` (cuántos enemigos deben quedar vivos para que entre la
siguiente oleada), `loop_waves` y `rewards` (`xp`, `credits`, `materials`, `blueprint`, `item_rarity`).

### Añadir un enemigo
En `config/enemies.json → enemies`: vida, escudo, velocidad, giro, `weapons` (identificadores de
`weapons.json`), `ai` y `model`.
- `ai`: `profile`, `detect_range`, `preferred_range`, `aggression`, `accuracy`, `evade_chance`,
  `retreat_hp`, `flank` y `missiles`.
- `model`: `hull` (uno de `dart`, `wedge`, `fork`, `heavy`, `station`, `alien`, `leviathan` o `void`),
  `scale` y tres colores.

Con `"static": true` el enemigo es una torreta fija.

### Añadir un jefe
En `enemies.json → bosses`: vida, escudo, `radius`, `weak_points`, `weak_point_hull`, `core_armor`,
`phases` (`threshold`, `patterns` de entre `spread`, `ring`, `missiles`, `beam` y `minions`, `interval`,
`minions`), `rewards` y `model` con `hull: "capital"` y `variant` (`warden`, `matriarch`, `dreadnought`,
`colossus` o `sovereign`). Para un comportamiento nuevo, añade un método `_p_<nombre>` en
`game/enemies/boss.py`.

### Añadir un arma
En `config/weapons.json`, con `slot` (`primary`, `secondary` o `special`) y `kind` (`projectile`, `beam`,
`missile`, `drones`, `pulse` o `torpedo`). Hay que indicar daño, cadencia, alcance, velocidad del proyectil,
consumo de energía, recarga, probabilidad de crítico, multiplicadores contra escudo y casco, radio de
explosión, nivel tecnológico, rareza, color, sonido y `unlock` (créditos y si necesita plano). Un tipo
(`kind`) nuevo requiere programar su disparo en `game/player/player_ship.py`.

### Mejoras y economía
Las mejoras están en `config/upgrades.json`: cada efecto indica una estadística de nave, su cambio por nivel
y si es porcentual. La economía está en `config/economy.json`: recompensas iniciales, curva de nivel,
rarezas, botín y precios de venta.

## 9. Pruebas

```bash
python -m pytest -q                         # pruebas unitarias
python tools/smoke_test.py                  # el juego real con piloto automático (recorrido rápido)
python tools/smoke_test.py --all            # toda la campaña
python tools/smoke_test.py --plan orion_boss --shots capturas
python tools/model_viewer.py                # visor de modelos
python tools/model_viewer.py evo.png --tiers vanguard   # las cinco etapas Mk I-V en una imagen
```
`smoke_test.py` abre la ventana real y juega con un piloto automático invulnerable. Recorre los menús (mapa,
hangar, configuración), juega las misiones, prueba una derrota (casco a 1 punto) y comprueba que la partida se
guarda y se vuelve a cargar. Usa una carpeta temporal, nunca `saves/`, y avisa si el registro contiene
errores.

## 10. Registro de pruebas realizadas

Ver la sección «Resultados» al final de este archivo.

## 11. Limitaciones conocidas

- **Modelos procedurales:** las naves se construyen con piezas facetadas, texturas de paneles y luces
  emisivas. Tienen identidad propia y se ven coherentes, pero no tienen el detalle de un modelo AAA hecho a
  mano. `assets/models/` está preparada para incorporar modelos externos con licencia compatible.
- **Audio sintetizado:** los sonidos y la música son síntesis sencillas (provisionales pero funcionales). Se
  pueden sustituir dejando WAV con el mismo nombre. El audio espacial se aproxima con atenuación por
  distancia y balance estéreo; no hay HRTF.
- **Mando:** el soporte usa la API de dispositivos de Panda3D, pero no se ha probado con un mando físico.
- **Reasignación de teclas:** acepta teclas y los tres botones del ratón; no permite combinaciones.
- **Equilibrio:** la dificultad se ajustó con un piloto automático; falta afinarla con partidas humanas
  (todos los valores están en `config/`).
- **Rendimiento:** solo se ha medido en un equipo. No hay escalado de resolución dinámico. Con muchos
  enemigos y partículas en el preajuste Alto puede bajar de 60 FPS en equipos modestos.
- **Cambio de calidad:** el MSAA y el tamaño de texturas de planetas se aplican al arrancar o en la siguiente
  misión.
- **Python 3.11:** el entorno virtual de desarrollo usa Python 3.13 porque 3.11 no estaba instalado; las
  dependencias admiten 3.11, pero no se ha ejecutado con esa versión.

## Resultados

Pruebas ejecutadas en Windows 11 (64 bits), Python 3.13.13, Panda3D 1.10.16, preajuste Alto, 1280×720.

**Pruebas unitarias:** `python -m pytest` → 58 pruebas superadas (configuración, progresión, evolución de la
nave, economía, combate, colisiones, misiones, IA, guardado y síntesis de audio).

**Juego real con piloto automático** (`tools/smoke_test.py`, ventana real, render, audio y lógica completos):

| Recorrido | Resultado |
|---|---|
| Menús: principal, ranuras, mapa, hangar (4 pestañas), configuración, pausa, resumen y derrota | Funcionan; capturas revisadas |
| Campaña completa (19 misiones) | 14 completadas a la primera; 0 errores internos; entre 44 y 57 FPS |
| Tras ajustar el Núcleo del Vacío | Legión de espectros (133 s) y Último bastión (95 s) completadas |
| Jefes atacados directamente con una nave Mk IV | Matriarca 111 s · Acorazado 181 s · Soberano 184 s · Coloso ≈ 230 s |
| Nave en etapa Mk V (nivel 16) | Ráfagas triples y modelo Mk V en juego; patrulla completada en 27 s (42 s con Mk I) |
| Derrota (casco a 1 punto) | Lleva a la pantalla de derrota; conserva la mitad de lo ganado |
| Guardar y volver a cargar | Nivel, créditos, misiones, galaxias y mejoras recuperados sin avisos |

**Errores encontrados y corregidos durante las pruebas** (resumen):
- Los generadores de los jefes quedaban dentro de las esferas de colisión del casco y eran imposibles de
  alcanzar: ahora tienen prioridad si el disparo los toca.
- Los jefes oscuros de la Nebulosa Carmesí eran invisibles a contraluz: se añadió una luz de relleno.
- Los cazas tenían esferas de impacto pequeñas y era muy difícil acertar: esferas algo mayores y asistencia
  de puntería de 4,5°.
- Los jefes invocaban refuerzos sin límite: ahora el jefe tiene como máximo 4 escoltas vivos.
- Recoger contenedores exigía pasar casi rozándolos: el radio de recogida y el imán se ampliaron.
- El sonido de alarma no se reproducía nunca: ahora suena con el casco crítico o con un misil entrante.
