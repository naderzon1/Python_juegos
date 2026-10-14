"""Aventura de plataformas 3D (Ursina), al estilo de los clásicos de correr y saltar.

Corre, salta, pisa a los enemigos, golpea los bloques "?" desde abajo, junta monedas
y llega a la bandera antes de que se acabe el tiempo.

Requiere:  pip install ursina
Los efectos y la música se generan solos la primera vez (carpeta sonidos_plataformas).

Controles:
  A / D  o  flechas izquierda / derecha  -> avanzar y retroceder
  W / S  o  flechas arriba / abajo       -> moverse en profundidad
  ESPACIO                                -> saltar (mantenlo pulsado para saltar más alto)
  SHIFT                                  -> correr
  M música  |  P pausa  |  R reiniciar  |  ESC salir
"""
import array
import math
import random
import wave
from pathlib import Path

from PIL import Image, ImageDraw
from ursina import (AmbientLight, Audio, DirectionalLight, Entity, Text, Texture, Ursina, Vec2, Vec3, application,
                    camera, color, curve, destroy, held_keys, invoke, time, window)
from ursina.shaders import lit_with_shadows_shader, unlit_shader

CARPETA = Path(__file__).resolve().parent / "sonidos_plataformas"

LARGO = 124.0            # largo del nivel
MEDIO_Z = 3.0            # medio ancho de la pista (profundidad)
GRAVEDAD = 32.0
VEL_SALTO = 12.5         # alcanza unas 2,4 unidades de altura
VEL_ANDAR, VEL_CORRER = 6.0, 9.5
VEL_REBOTE = 9.0         # impulso al pisar un enemigo
MEDIO, ALTO = 0.35, 1.3  # medio ancho y altura del héroe
VIDAS = 3
TIEMPO = 200             # segundos para terminar el nivel
X_CONTROL = 60.0         # punto de control: al perder una vida se reaparece aquí
X_META = 114.0
Y_BLOQUE = 3.0           # altura de la base de los bloques flotantes
VOL_MUSICA = 0.55
EPS = 1e-4

PIEDRA, NARANJA, AMARILLO = "#9e9e9e", "#ef6c00", "#fdd835"

# --- nivel --------------------------------------------------------------------
SUELO = [(0, 24), (27, 50), (58, 84), (92, LARGO)]  # tramos de suelo (x inicial, x final); entre ellos hay vacío
# cajas fijas: x inicial, x final, altura de arriba, grosor, z inicial, z final, color
CAJAS = [
    (17, 18.5, 1.2, 1.2, 0.5, 3, PIEDRA),
    (32, 36, 2.0, 0.6, -1.5, 1.5, NARANJA), (38, 41, 3.6, 0.6, -1.5, 1.5, NARANJA),
    (72, 74, 1, 1, -3, 3, PIEDRA), (74, 76, 2, 2, -3, 3, PIEDRA), (76, 84, 3, 3, -3, 3, PIEDRA),
    (106, 108, 1, 1, -3, 3, PIEDRA), (108, 110, 2, 2, -3, 3, PIEDRA),
]
# plataformas móviles: x, altura de arriba, z, eje que recorren, amplitud, periodo en segundos
MOVILES = [(54.0, 0.0, 0, "x", 2.0, 5.0), (88.0, 1.75, 0, "y", 1.25, 4.5)]
# bloques flotantes: x, z, tipo ("?" suelta una moneda, "L" es un ladrillo)
BLOQUES = [(8, 0, "?"), (9, 0, "L"), (10, 0, "?"), (11, 0, "L"), (44, 1, "L"), (45, 1, "?"), (46, 1, "L"),
           (63, -1, "?"), (64, -1, "?"), (65, -1, "?"), (98, 0, "L"), (99, 0, "?"), (100, 0, "L")]
# enemigos: x, altura del piso, z, x mínima, x máxima, velocidad
ENEMIGOS = [(14, 0, 0, 11, 16.5, 1.8), (30, 0, -1.5, 28, 36, 2.0), (34, 2.0, 0, 32.5, 35.5, 1.2),
            (44, 0, 1.5, 38, 49, 2.2), (62, 0, 1, 59, 70, 2.2), (67, 0, -1.5, 59, 71, 3.0), (80, 3, 0, 77, 83, 1.8),
            (98, 0, 1, 93, 105, 2.4), (102, 0, -1.5, 93, 105, 3.0)]


def fila(x, n, y, z, paso=1.0):
    return [(x + i * paso, y, z) for i in range(n)]


MONEDAS = (fila(4, 3, 1, 0) + fila(13, 3, 1, -2) + fila(20, 2, 1, 2) + [(24.6, 2.0, 0), (25.5, 2.5, 0), (26.4, 2.0, 0)]
           + fila(33, 3, 3, 0) + fila(38.8, 3, 4.6, 0, 0.7) + fila(47, 2, 1, -1.5) + fila(52, 3, 1.2, 0, 2)
           + fila(60, 3, 1, 1) + fila(68, 2, 1, -2) + [(73, 2, 0), (75, 3, 0)] + fila(78, 4, 4, 0, 1.5)
           + [(88, 4.4, 0)] + fila(94, 3, 1, 0) + fila(103, 3, 1, 2) + [(107, 2, 0), (109, 3, 0)])

# --- sonido: todo se sintetiza aquí, sin archivos externos ----------------------
FREC = 22050   # muestras por segundo
PASO = 0.2     # duración de una corchea de la música (150 pulsos por minuto)
# melodía y bajo propios, como (nota MIDI o None para silencio, duración en corcheas)
MELODIA = [(72, 1), (76, 1), (79, 1), (76, 1), (84, 2), (79, 2),
           (77, 1), (81, 1), (84, 1), (81, 1), (79, 2), (76, 2),
           (74, 1), (77, 1), (81, 1), (77, 1), (79, 1), (76, 1), (72, 2),
           (74, 1), (76, 1), (77, 1), (74, 1), (67, 3), (None, 1),
           (76, 1), (79, 1), (84, 1), (79, 1), (76, 2), (72, 2),
           (81, 1), (84, 1), (88, 1), (84, 1), (81, 2), (76, 2),
           (77, 1), (81, 1), (84, 1), (81, 1), (79, 1), (83, 1), (86, 2),
           (84, 2), (79, 1), (76, 1), (72, 3), (None, 1)]
BAJO = [nota for raiz in (48, 48, 53, 53, 50, 50, 43, 43, 48, 48, 45, 45, 41, 43, 48, 48)
        for nota in ((raiz, 2), (raiz + 7, 2))]


def hz(nota):
    """Frecuencia de una nota MIDI (69 = la de 440 Hz)."""
    return 440 * 2 ** ((nota - 69) / 12)


def tono(pista, inicio, dur, f0, f1=None, vol=0.3, onda="cuadrada"):
    """Suma a la pista un sonido que se desliza de f0 a f1 Hz."""
    f1 = f0 if f1 is None else f1
    i0, n = int(inicio * FREC), int(dur * FREC)
    pista.extend([0.0] * (i0 + n - len(pista)))
    fase = 0.0
    for k in range(n):
        t = k / n
        fase = (fase + (f0 + (f1 - f0) * t) / FREC) % 1
        if onda == "cuadrada":
            v = 1.0 if fase < 0.5 else -1.0
        elif onda == "triangular":
            v = 4 * abs(fase - 0.5) - 1
        else:  # ruido
            v = random.uniform(-1, 1)
        # ataque y final suaves para que no haga "clic", y una caída ligera
        pista[i0 + k] += vol * v * min(1.0, k / 100, (n - k) / 400) * (1 - 0.6 * t)


def melodia(pista, notas, paso, vol, onda):
    t = 0.0
    for nota, pasos in notas:
        if nota is not None:
            tono(pista, t, pasos * paso * 0.92, hz(nota), vol=vol, onda=onda)
        t += pasos * paso


def componer(nombre):
    p = []
    if nombre == "salto":
        tono(p, 0, 0.2, 300, 900)
    elif nombre == "moneda":
        melodia(p, [(84, 1), (88, 1), (91, 4)], 0.055, 0.3, "cuadrada")
    elif nombre == "pisar":
        tono(p, 0, 0.16, 420, 70, vol=0.35)
        tono(p, 0, 0.08, 0, vol=0.25, onda="ruido")
    elif nombre == "bloque":
        tono(p, 0, 0.09, 190, 110, vol=0.4)
    elif nombre == "golpe":
        melodia(p, [(72, 1), (68, 1), (65, 1), (60, 3)], 0.09, 0.3, "cuadrada")
    elif nombre == "control":
        melodia(p, [(79, 1), (84, 3)], 0.09, 0.35, "triangular")
    elif nombre == "victoria":
        melodia(p, [(72, 1), (76, 1), (79, 1), (84, 1), (88, 1), (91, 1), (96, 6)], 0.11, 0.25, "cuadrada")
        melodia(p, [(48, 3), (55, 3), (60, 6)], 0.11, 0.3, "triangular")
    elif nombre == "fin":
        melodia(p, [(72, 2), (67, 2), (64, 2), (60, 5)], 0.16, 0.35, "triangular")
    else:  # musica: debe durar justo 8 compases para repetirse sin corte
        melodia(p, MELODIA, PASO, 0.15, "cuadrada")
        melodia(p, BAJO, PASO, 0.3, "triangular")
        n = int(64 * PASO * FREC)
        p = (p + [0.0] * n)[:n]
    return p


def crear_sonidos():
    """Genera los archivos de sonido que falten y devuelve {nombre: ruta}."""
    CARPETA.mkdir(exist_ok=True)
    rutas = {}
    for nombre in ("salto", "moneda", "pisar", "bloque", "golpe", "control", "victoria", "fin", "musica"):
        rutas[nombre] = CARPETA / f"{nombre}.wav"
        if not rutas[nombre].exists():
            datos = array.array("h", (int(max(-1.0, min(1.0, v)) * 32000) for v in componer(nombre)))
            with wave.open(str(rutas[nombre]), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(FREC)
                w.writeframes(datos.tobytes())
    return rutas


# --- gráficos -------------------------------------------------------------------
def rgba(hexa, a=1.0):
    c = color.hex(hexa)
    return color.Color(c[0], c[1], c[2], a)


def crear_texturas():
    """Texturas pixeladas dibujadas a mano: bloque "?", bloque gastado, ladrillo y pasto."""
    def lienzo(fondo, borde):
        img = Image.new("RGB", (32, 32), fondo)
        ImageDraw.Draw(img).rectangle((0, 0, 31, 31), outline=borde, width=2)
        return img

    interrogacion = ["..XXXX..", ".XX..XX.", ".....XX.", "....XX..", "...XX...", "...XX...", "........", "...XX..."]
    sorpresa = lienzo("#fbc02d", "#e65100")
    d = ImageDraw.Draw(sorpresa)
    for (dx, dy), tinta in (((1, 1), "#8d4a00"), ((0, 0), "#ffffff")):  # sombra y luego el signo
        for fy, linea in enumerate(interrogacion):
            for fx, c in enumerate(linea):
                if c == "X":
                    d.rectangle((4 + fx * 3 + dx, 4 + fy * 3 + dy, 6 + fx * 3 + dx, 6 + fy * 3 + dy), fill=tinta)

    ladrillo = Image.new("RGB", (32, 32), "#bf5a2e")
    d = ImageDraw.Draw(ladrillo)
    for y in range(0, 32, 8):
        d.line((0, y, 31, y), fill="#5d2a12")
        for x in range(0 if (y // 8) % 2 == 0 else 8, 32, 16):
            d.line((x, y, x, y + 8), fill="#5d2a12")

    pasto = Image.new("RGB", (2, 2), "#4caf50")
    pasto.putpixel((0, 0), (67, 160, 71))
    pasto.putpixel((1, 1), (67, 160, 71))

    texturas = {"?": Texture(sorpresa), "gastado": Texture(lienzo("#8d6e63", "#4e342e")), "L": Texture(ladrillo),
                "pasto": Texture(pasto)}
    for t in texturas.values():
        t.filtering = None
    return texturas


class Solido:
    """Caja con la que choca el héroe: centro (cx, cy, cz) y medias medidas (mx, my, mz)."""

    def __init__(self, x0, x1, y0, y1, z0, z1):
        self.cx, self.cy, self.cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
        self.mx, self.my, self.mz = (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2
        self.dx = self.dy = 0.0  # cuánto se movió en este cuadro (plataformas móviles)
        self.tipo = ""           # "?" o "L" si es un bloque
        self.usado = False
        self.vista = None


def acercar(valor, objetivo, paso):
    """Mueve valor hacia objetivo sin pasarse."""
    if valor < objetivo:
        return min(valor + paso, objetivo)
    return max(valor - paso, objetivo)


def pulsada(*teclas):
    return any(held_keys[t] for t in teclas)


class Juego(Entity):
    def __init__(self):
        super().__init__()
        rutas = crear_sonidos()
        self.sonidos = {n: Audio(r, autoplay=False) for n, r in rutas.items() if n != "musica"}
        self.musica = Audio(rutas["musica"], autoplay=False, loop=True, volume=VOL_MUSICA)
        self.con_musica = True
        self.texturas = crear_texturas()
        self.monedas, self.enemigos = [], []
        self.crear_nivel()
        self.crear_heroe()
        self.crear_hud()
        self.reiniciar()

    # --- escenario ------------------------------------------------------------
    def cubo(self, s, **kw):
        return Entity(parent=self.nivel, model="cube", position=(s.cx, s.cy, s.cz),
                      scale=(2 * s.mx, 2 * s.my, 2 * s.mz), **kw)

    def crear_nivel(self):
        window.color = rgba("#7ec8f0")
        camera.fov = 50
        camera.rotation = (15, 0, 0)
        self.nivel = Entity()
        self.solidos, self.moviles, self.bloques = [], [], []

        for x0, x1 in SUELO:
            s = Solido(x0, x1, -2.5, 0, -MEDIO_Z, MEDIO_Z)
            Entity(parent=self.nivel, model="cube", position=(s.cx, -1.4, 0), scale=(x1 - x0, 2.2, 2 * MEDIO_Z),
                   color=rgba("#8d5a3b"))
            Entity(parent=self.nivel, model="cube", position=(s.cx, -0.15, 0), scale=(x1 - x0, 0.3, 2 * MEDIO_Z),
                   texture=self.texturas["pasto"], texture_scale=((x1 - x0) / 2, MEDIO_Z))
            self.solidos.append(s)
        for x0, x1, arriba, grosor, z0, z1, hexa in CAJAS:
            s = Solido(x0, x1, arriba - grosor, arriba, z0, z1)
            s.vista = self.cubo(s, color=rgba(hexa))
            self.solidos.append(s)
        for x, arriba, z, eje, amplitud, periodo in MOVILES:
            s = Solido(x - 1.5, x + 1.5, arriba - 0.6, arriba, z - 1.5, z + 1.5)
            s.vista = self.cubo(s, color=rgba(AMARILLO))
            s.eje, s.base, s.amplitud, s.periodo = eje, (s.cx if eje == "x" else s.cy), amplitud, periodo
            self.solidos.append(s)
            self.moviles.append(s)
        for x, z, tipo in BLOQUES:
            s = Solido(x - 0.5, x + 0.5, Y_BLOQUE, Y_BLOQUE + 1, z - 0.5, z + 0.5)
            s.tipo = tipo
            s.vista = self.cubo(s, texture=self.texturas[tipo])
            self.solidos.append(s)
            self.bloques.append(s)

        # bandera de meta y banderín del punto de control
        Entity(parent=self.nivel, model="cube", position=(X_META, 3, 0), scale=(0.14, 6, 0.14), color=rgba("#eceff1"))
        Entity(parent=self.nivel, model="sphere", position=(X_META, 6.1, 0), scale=0.4, color=rgba(AMARILLO))
        Entity(parent=self.nivel, model="cube", position=(X_META + 0.75, 5.3, 0), scale=(1.4, 1.0, 0.06),
               color=rgba("#e53935"))
        Entity(parent=self.nivel, model="cube", position=(X_META, 0.2, 0), scale=(0.9, 0.4, 0.9), color=rgba(PIEDRA))
        Entity(parent=self.nivel, model="cube", position=(X_CONTROL, 1, 2.6), scale=(0.1, 2, 0.1),
               color=rgba("#eceff1"))
        self.banderin = Entity(parent=self.nivel, model="cube", position=(X_CONTROL + 0.4, 1.7, 2.6),
                               scale=(0.7, 0.5, 0.05))

        # decorado lejano: colinas y nubes (no forma parte del nivel ni hace sombra)
        rnd = random.Random(5)
        for x in range(-10, int(LARGO) + 30, 14):
            Entity(model="sphere", position=(x + rnd.uniform(-3, 3), -3, rnd.uniform(14, 24)), shader=unlit_shader,
                   scale=(rnd.uniform(12, 20), rnd.uniform(8, 14), 10),
                   color=rgba(rnd.choice(["#66bb6a", "#81c784", "#5aa95e"])))
            nube = Entity(position=(x + rnd.uniform(-5, 5), rnd.uniform(9, 14), rnd.uniform(16, 28)))
            for dx, esc in ((-1.6, 1.8), (0, 2.6), (1.7, 2.0)):
                Entity(parent=nube, model="sphere", x=dx, scale=(esc * 1.3, esc * 0.8, esc), color=color.white,
                       shader=unlit_shader)

        sol = DirectionalLight(shadows=True, shadow_map_resolution=Vec2(2048, 2048))
        sol.look_at(Vec3(0.4, -1, 0.6))
        sol.update_bounds(self.nivel)
        AmbientLight(color=color.Color(0.5, 0.5, 0.55, 1))

    def crear_heroe(self):
        h = self.heroe = Entity()
        azul, verde, piel = rgba("#283593"), rgba("#00897b"), rgba("#ffcc99")
        self.piernas, self.brazos = [], []
        for lado in (-1, 1):
            cadera = Entity(parent=h, position=(lado * 0.16, 0.45, 0))
            Entity(parent=cadera, model="cube", y=-0.22, scale=(0.22, 0.45, 0.26), color=azul)
            self.piernas.append(cadera)
            hombro = Entity(parent=h, position=(lado * 0.4, 0.92, 0))
            Entity(parent=hombro, model="cube", y=-0.2, scale=(0.15, 0.42, 0.2), color=piel)
            self.brazos.append(hombro)
            Entity(parent=h, model="sphere", position=(lado * 0.1, 1.14, 0.22), scale=0.08, color=color.black)
        Entity(parent=h, model="cube", y=0.7, scale=(0.62, 0.5, 0.4), color=verde)
        Entity(parent=h, model="sphere", y=1.12, scale=0.5, color=piel)
        Entity(parent=h, model="sphere", y=1.27, scale=(0.54, 0.26, 0.54), color=rgba(AMARILLO))
        Entity(parent=h, model="cube", position=(0, 1.22, 0.3), scale=(0.4, 0.05, 0.3), color=rgba(AMARILLO))
        # sombra redonda bajo el héroe: ayuda a calcular dónde va a caer
        self.sombra = Entity(model="sphere", scale=(0.8, 0.02, 0.8), color=rgba("#000000", 0.35), shader=unlit_shader)

    def crear_enemigo(self, x, piso, z, x_min, x_max, vel):
        e = Entity(position=(x, piso, z))
        e.cuerpo = Entity(parent=e, model="sphere", y=0.42, scale=(0.9, 0.8, 0.9), color=rgba("#7e57c2"))
        for lado in (-1, 1):
            Entity(parent=e, model="sphere", position=(lado * 0.17, 0.55, 0.36), scale=0.2, color=color.white)
            Entity(parent=e, model="sphere", position=(lado * 0.17, 0.55, 0.44), scale=0.09, color=color.black)
            Entity(parent=e, model="cube", position=(lado * 0.22, 0.07, 0.05), scale=(0.28, 0.14, 0.4),
                   color=rgba("#4527a0"))
        e.x_min, e.x_max, e.vel = x_min, x_max, vel
        return e

    def crear_moneda(self, pos):
        return Entity(model="sphere", position=pos, scale=(0.55, 0.55, 0.12), color=rgba("#ffca28"))

    def crear_hud(self):
        ui = camera.ui
        Entity(parent=ui, model="quad", position=(0, 0.465, 0.1), scale=(2, 0.07), color=rgba("#0d1b2a", 0.6))
        Entity(parent=ui, model="quad", position=(0, -0.47, 0.1), scale=(2, 0.05), color=rgba("#0d1b2a", 0.6))
        self.marcador = Text(parent=ui, origin=(0, 0), position=(0, 0.465), scale=1.15)
        Text(parent=ui, origin=(0, 0), position=(0, -0.47), scale=0.75,
             text="A/D avanzar   W/S profundidad   ESPACIO saltar   SHIFT correr   |   M música   P pausa   R reiniciar")
        self.panel = Entity(parent=ui, model="quad", position=(0, 0.27, 0.1), scale=(1.0, 0.22),
                            color=rgba("#0d1b2a", 0.65), enabled=False)
        self.titulo = Text(parent=ui, origin=(0, 0), position=(0, 0.3), scale=3)
        self.subtitulo = Text(parent=ui, origin=(0, 0), position=(0, 0.21), scale=1.1)

    # --- estado ---------------------------------------------------------------
    def reiniciar(self):
        for e in self.monedas + self.enemigos:
            destroy(e)
        self.monedas = [self.crear_moneda(p) for p in MONEDAS]
        self.enemigos = [self.crear_enemigo(*d) for d in ENEMIGOS]
        for b in self.bloques:
            b.usado = False
            b.vista.texture = self.texturas[b.tipo]
        self.puntos = self.n_monedas = 0
        self.vidas = VIDAS
        self.tiempo = float(TIEMPO)
        self.reloj = 0.0
        self.x_reaparicion = 2.0
        self.banderin.color = rgba("#b0bec5")
        self.estado = "jugando"  # jugando, ganado o fin
        self.pausa = False
        self.reaparecer()
        camera.position = self.punto_camara()
        self.ajustar_musica()
        self.musica.play()
        self.actualizar_hud()

    def reaparecer(self):
        self.px, self.py, self.pz = self.x_reaparicion, 0.0, 0.0
        self.vx = self.vy = self.vz = 0.0
        self.en_suelo = False
        self.apoyo = None      # sólido sobre el que está parado
        self.t_pedido = 0.0    # margen: salto pedido un instante antes de tocar el suelo
        self.t_suelo = 0.0     # margen: todavía puede saltar justo al salir de un borde
        self.t_inmune = 0.0
        self.rumbo = 90.0      # hacia dónde mira

    def sonar(self, nombre):
        self.sonidos[nombre].play()

    def ajustar_musica(self):
        self.musica.volume = VOL_MUSICA if self.con_musica and not self.pausa else 0

    def input(self, key):
        if key == "space" and self.estado == "jugando" and not self.pausa:
            self.t_pedido = 0.12
        elif key == "r":
            self.reiniciar()
        elif key == "p" and self.estado == "jugando":
            self.pausa = not self.pausa
            self.ajustar_musica()
            self.actualizar_hud()
        elif key == "m":
            self.con_musica = not self.con_musica
            self.ajustar_musica()
        elif key == "escape":
            application.quit()

    def perder_vida(self):
        self.vidas -= 1
        if self.vidas <= 0:
            self.terminar("fin")
        else:
            self.sonar("golpe")
            self.reaparecer()
            self.t_inmune = 2.0

    def terminar(self, estado):
        self.estado = estado
        self.musica.clip.stop()
        if estado == "ganado":
            self.puntos += int(self.tiempo) * 10
            self.sonar("victoria")
        else:
            self.sonar("fin")

    # --- lógica ---------------------------------------------------------------
    def solidos_en(self, x, y, z):
        """Sólidos que se cruzan con la caja del héroe puesta en (x, y, z)."""
        return [s for s in self.solidos
                if abs(x - s.cx) < MEDIO + s.mx - EPS and abs(z - s.cz) < MEDIO + s.mz - EPS
                and y < s.cy + s.my - EPS and y + ALTO > s.cy - s.my + EPS]

    def mover_plataformas(self, dt):
        self.reloj += dt
        for s in self.moviles:
            nuevo = s.base + s.amplitud * math.sin(2 * math.pi * self.reloj / s.periodo)
            if s.eje == "x":
                s.dx, s.cx = nuevo - s.cx, nuevo
            else:
                s.dy, s.cy = nuevo - s.cy, nuevo
            s.vista.position = (s.cx, s.cy, s.cz)
        # la plataforma lleva encima al héroe
        if self.apoyo is not None and self.estado == "jugando":
            self.px += self.apoyo.dx
            self.py += self.apoyo.dy

    def mover_heroe(self, dt):
        dx = pulsada("d", "right arrow") - pulsada("a", "left arrow")
        dz = pulsada("w", "up arrow") - pulsada("s", "down arrow")
        vel = VEL_CORRER if pulsada("shift", "left shift", "right shift") else VEL_ANDAR
        if dx and dz:
            vel *= 0.75
        acel = (60 if self.en_suelo else 35) * dt
        self.vx = acercar(self.vx, dx * vel, acel)
        self.vz = acercar(self.vz, dz * vel * 0.8, acel)

        self.t_pedido -= dt
        self.t_suelo -= dt
        if self.t_pedido > 0 and self.t_suelo > 0:
            self.vy = VEL_SALTO
            self.t_pedido = self.t_suelo = 0.0
            self.sonar("salto")
        if self.vy > 5 and not held_keys["space"]:
            self.vy = 5.0  # salto corto si se suelta la tecla
        self.vy = max(self.vy - GRAVEDAD * dt, -22.0)

        # se resuelve un eje cada vez: así el héroe resbala por las paredes en vez de atascarse
        x = self.px + self.vx * dt
        for s in self.solidos_en(x, self.py, self.pz):
            x = s.cx - s.mx - MEDIO if x < s.cx else s.cx + s.mx + MEDIO
            self.vx = 0.0
        self.px = max(MEDIO, min(LARGO - MEDIO, x))

        z = self.pz + self.vz * dt
        for s in self.solidos_en(self.px, self.py, z):
            z = s.cz - s.mz - MEDIO if z < s.cz else s.cz + s.mz + MEDIO
            self.vz = 0.0
        self.pz = max(-MEDIO_Z + MEDIO, min(MEDIO_Z - MEDIO, z))

        y = self.py + self.vy * dt
        self.en_suelo, self.apoyo = False, None
        bajando = self.vy <= 0  # se decide antes: puede tocar dos sólidos en el mismo cuadro
        for s in self.solidos_en(self.px, y, self.pz):
            if bajando:
                y = max(y, s.cy + s.my)
                self.en_suelo, self.apoyo, self.t_suelo = True, s, 0.1
            else:
                y = min(y, s.cy - s.my - ALTO)
                self.golpear_bloque(s)
            self.vy = 0.0
        self.py = y

        if self.py < -8:
            self.perder_vida()
        elif self.px >= X_META - 0.5:
            self.terminar("ganado")
        elif self.px >= X_CONTROL and self.x_reaparicion < X_CONTROL:
            self.x_reaparicion = X_CONTROL
            self.banderin.color = rgba("#43a047")
            self.sonar("control")

    def golpear_bloque(self, s):
        if not s.tipo:
            return
        s.vista.animate_y(s.cy + 0.25, duration=0.08, curve=curve.out_quad)
        invoke(s.vista.animate_y, s.cy, duration=0.1, delay=0.08)
        if s.tipo == "?" and not s.usado:
            s.usado = True
            s.vista.texture = self.texturas["gastado"]
            self.n_monedas += 1
            self.puntos += 50
            self.sonar("moneda")
            m = self.crear_moneda((s.cx, s.cy + 0.9, s.cz))
            m.animate_y(s.cy + 2.3, duration=0.3, curve=curve.out_quad)
            destroy(m, delay=0.35)
        else:
            self.sonar("bloque")

    def mover_enemigos(self, dt):
        for e in list(self.enemigos):
            e.x += e.vel * dt
            if e.x >= e.x_max:
                e.vel = -abs(e.vel)
            elif e.x <= e.x_min:
                e.vel = abs(e.vel)
            e.rotation_y = 90 if e.vel > 0 else -90
            e.cuerpo.rotation_z = 8 * math.sin(self.reloj * 9)
            toca = (abs(self.px - e.x) < MEDIO + 0.45 and abs(self.pz - e.z) < MEDIO + 0.45
                    and self.py < e.y + 0.8 and self.py + ALTO > e.y)
            if not toca:
                continue
            if self.vy < 0 and self.py > e.y + 0.3:  # cae sobre él: lo aplasta y rebota
                self.enemigos.remove(e)
                e.scale_y = 0.25
                destroy(e, delay=0.35)
                self.vy = VEL_REBOTE
                self.puntos += 100
                self.sonar("pisar")
            elif self.t_inmune <= 0:
                self.perder_vida()
                break

    def recoger_monedas(self):
        for m in list(self.monedas):
            if abs(m.x - self.px) < 0.8 and abs(m.y - self.py - ALTO / 2) < 1.0 and abs(m.z - self.pz) < 0.8:
                self.monedas.remove(m)
                destroy(m)
                self.n_monedas += 1
                self.puntos += 50
                self.sonar("moneda")

    # --- dibujo ---------------------------------------------------------------
    def punto_camara(self):
        return Vec3(self.px + 3.5, 6.5 + max(self.py, 0) * 0.5, -20)

    def animar(self, dt):
        h = self.heroe
        h.position = (self.px, self.py, self.pz)
        if abs(self.vx) + abs(self.vz) > 0.5:
            self.rumbo = math.degrees(math.atan2(self.vx, self.vz))
        h.rotation_y += ((self.rumbo - h.rotation_y + 180) % 360 - 180) * min(1, 14 * dt)
        paso = 0.0
        if self.en_suelo:
            paso = 40 * math.sin(self.reloj * 14) * min(1, (abs(self.vx) + abs(self.vz)) / VEL_ANDAR)
        for i, (pierna, brazo) in enumerate(zip(self.piernas, self.brazos)):
            pierna.rotation_x = paso if i == 0 else -paso
            brazo.rotation_x = (-paso if i == 0 else paso) if self.en_suelo else -150  # brazos arriba en el aire
        self.t_inmune = max(0.0, self.t_inmune - dt)
        h.enabled = self.estado != "fin" and (self.t_inmune <= 0 or int(self.reloj * 14) % 2 == 0)

        # la sombra se apoya en lo más alto que haya debajo del héroe
        pisos = [s.cy + s.my for s in self.solidos
                 if abs(self.px - s.cx) < s.mx and abs(self.pz - s.cz) < s.mz and s.cy + s.my <= self.py + 0.05]
        self.sombra.enabled = bool(pisos) and h.enabled
        if pisos:
            self.sombra.position = (self.px, max(pisos) + 0.02, self.pz)

        for m in self.monedas:
            m.rotation_y += 200 * dt
        camera.position += (self.punto_camara() - camera.position) * min(1, 5 * dt)

    def actualizar_hud(self):
        marcador = (f"PUNTOS {self.puntos:06d}        MONEDAS {self.n_monedas:02d}        VIDAS {self.vidas}"
                    f"        TIEMPO {max(0, math.ceil(self.tiempo)):03d}")
        if marcador != self.marcador.text:
            self.marcador.text = marcador
        if self.estado == "ganado":
            titulo, sub, tinta = "¡NIVEL COMPLETADO!", f"Puntos: {self.puntos}   |   R para jugar de nuevo", "#a5d6a7"
        elif self.estado == "fin":
            titulo, sub, tinta = "FIN DEL JUEGO", "Presiona R para volver a intentarlo", "#ef9a9a"
        elif self.pausa:
            titulo, sub, tinta = "PAUSA", "Presiona P para seguir", "#ffffff"
        else:
            titulo, sub, tinta = "", "", "#ffffff"
        if titulo != self.titulo.text:
            self.titulo.text, self.titulo.color, self.subtitulo.text = titulo, rgba(tinta), sub
            self.panel.enabled = bool(titulo)

    def update(self):
        if self.pausa:
            return
        dt = min(time.dt, 1 / 20)
        self.mover_plataformas(dt)
        if self.estado == "jugando":
            # pasos cortos para no atravesar plataformas delgadas si baja la velocidad de cuadros
            pasos = max(1, math.ceil(dt * 120))
            for _ in range(pasos):
                if self.estado == "jugando":
                    self.mover_heroe(dt / pasos)
        if self.estado == "jugando":
            self.mover_enemigos(dt)
        if self.estado == "jugando":
            self.recoger_monedas()
            self.tiempo -= dt
            if self.tiempo <= 0:
                self.tiempo = float(TIEMPO)
                self.perder_vida()
        self.animar(dt)
        self.actualizar_hud()


def crear_app():
    # Ursina busca recursos en toda la carpeta del script; se limita a la de sonidos para que arranque rápido
    CARPETA.mkdir(exist_ok=True)
    application.asset_folder = CARPETA
    app = Ursina(title="Aventura de plataformas 3D", size=(1200, 720), borderless=False, fullscreen=False,
                 development_mode=False, editor_ui_enabled=False)
    Entity.default_shader = lit_with_shadows_shader
    return app, Juego()


if __name__ == "__main__":
    app, juego = crear_app()
    app.run()
