"""Duelo de naves 3D (Ursina), con tres modos de juego:

  PC vs USUARIO       -> tú contra el computador
  PC vs 2 USUARIOS    -> dos jugadores en equipo contra el computador
  USUARIO vs USUARIO  -> un jugador contra el otro

Requiere:  pip install ursina

Controles:
  JUGADOR 1 (azul)  : A / D mover,  W o ESPACIO disparar
  JUGADOR 2         : flechas izquierda / derecha mover,  flecha arriba o ENTER disparar
                      (verde y cerca si juega en equipo; naranja y lejos si es el rival)
  (en PC vs USUARIO también puedes mover con las flechas)
  M          -> cambiar modo
  1 / 2 / 3  -> dificultad del computador (fácil / media / difícil)
  P pausa  |  R reiniciar partida  |  ESC salir
Gana el bando que deje al otro sin vida.
"""
import math
import random

from PIL import Image
from ursina import (AmbientLight, Cone, DirectionalLight, Entity, Grid, Mesh, Text, Texture, Ursina, Vec3,
                    application, camera, color, destroy, held_keys, time, window)
from ursina.shaders import lit_with_shadows_shader, unlit_shader

LIMITE_X = 9.5           # medio ancho del campo
Z_NAVE = (-8.0, 8.0)     # bando 0 cerca de la cámara, bando 1 al fondo
VIDA = 10
VEL_NAVE = 11.0          # unidades por segundo
VEL_BALA = 17.0
ENFRIAMIENTO = 0.3       # segundos entre disparos humanos

# modos de juego: M los recorre en este orden
UNO, EQUIPO, DUELO = 0, 1, 2
MODO = ("PC vs USUARIO", "PC vs 2 USUARIOS", "USUARIO vs USUARIO")
FINAL = (("¡VICTORIA!", "DERROTA"), ("¡GANA EL EQUIPO!", "GANÓ EL COMPUTADOR"), ("¡GANA JUGADOR 1!", "¡GANA JUGADOR 2!"))

# nave 0: jugador 1 | nave 1: computador o jugador 2 rival | nave 2: jugador 2 aliado (solo en equipo)
BANDO = (0, 1, 0)
HEX = ("#4fc3f7", "#ff7043", "#81c784")
HEX_BALA = ("#b3ecff", "#ffd0c2", "#c8e6c9")
TECLAS_SOLO = (("a", "left arrow"), ("d", "right arrow"), ("w", "space"))
TECLAS_J1 = (("a",), ("d",), ("w", "space"))
TECLAS_J2 = (("left arrow",), ("right arrow",), ("up arrow", "enter"))

# contra dos jugadores el computador tiene el doble de vida y dispara más seguido
VIDA_PC_EQUIPO = 2
CADENCIA_PC_EQUIPO = 0.7

# nombre, velocidad nave IA, enfriamiento de disparo IA (s), prob. de esquivar, error de puntería
DIFICULTAD = {1: ("Fácil", 4.5, 0.90, 0.30, 2.6), 2: ("Media", 6.5, 0.62, 0.70, 1.3), 3: ("Difícil", 9.0, 0.42, 0.95, 0.4)}


def rgba(hexa, a=1.0):
    c = color.hex(hexa)
    return color.Color(c[0], c[1], c[2], a)


def textura_resplandor(n=128):
    """Mancha circular difuminada: sirve para nebulosas y destellos."""
    img = Image.new("RGBA", (n, n))
    px = []
    for y in range(n):
        for x in range(n):
            d = math.hypot(x - n / 2, y - n / 2) / (n / 2)
            px.append((255, 255, 255, int(255 * max(0.0, 1 - d) ** 2)))
    img.putdata(px)
    return Texture(img)


def malla_anillo(r1, r2, seg=72):
    """Anillo plano (para el planeta)."""
    verts, tris = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        verts += [Vec3(math.cos(a) * r1, 0, math.sin(a) * r1), Vec3(math.cos(a) * r2, 0, math.sin(a) * r2)]
    for i in range(seg):
        a, b, c, d = 2 * i, 2 * i + 1, (2 * i + 2) % (2 * seg), (2 * i + 3) % (2 * seg)
        tris += [a, b, c, b, d, c]
    return Mesh(vertices=verts, triangles=tris)


def crear_nave(indice):
    """Nave hecha con primitivas: fuselaje, alas, cabina y motor."""
    base = rgba(HEX[indice])
    oscuro = color.Color(base[0] * 0.45, base[1] * 0.45, base[2] * 0.45, 1)
    nave = Entity(position=(0, 0, Z_NAVE[BANDO[indice]]), rotation_y=0 if BANDO[indice] == 0 else 180)
    Entity(parent=nave, model=Cone(resolution=14, radius=0.45, height=1.9), rotation_x=90, z=0.15, color=base)
    Entity(parent=nave, model="cube", scale=(2.3, 0.08, 0.75), z=-0.35, color=oscuro)
    for lado in (-1, 1):
        Entity(parent=nave, model="cube", scale=(0.12, 0.34, 1.05), position=(lado * 1.15, 0, -0.3), color=base)
        Entity(parent=nave, model="cube", scale=(0.1, 0.1, 0.6), position=(lado * 0.6, 0.06, 0.2),
               color=rgba("#cfd8dc"))
    Entity(parent=nave, model="sphere", scale=(0.3, 0.26, 0.5), position=(0, 0.2, -0.25), color=rgba("#e1f5fe"))
    nave.motor = Entity(parent=nave, model="sphere", scale=0.4, z=-0.9, color=rgba("#ffd54f"), shader=unlit_shader)
    return nave


class Juego(Entity):
    def __init__(self):
        super().__init__()
        self.modo = UNO
        self.nivel = 2
        self.victorias = [0, 0]  # por bando
        self.balas = []
        self.particulas = []
        self.crear_escenario()
        self.naves = [crear_nave(i) for i in range(len(BANDO))]
        self.crear_hud()
        self.reiniciar()

    # --- escenario: espacio exterior ----------------------------------------
    def crear_escenario(self):
        window.color = rgba("#03040c")
        camera.position = (0, 15, -25)
        camera.look_at(Vec3(0, 0, -1.5))
        camera.fov = 62

        sol = DirectionalLight(shadows=True)
        sol.look_at(Vec3(0.6, -1, 0.8))
        AmbientLight(color=color.Color(0.22, 0.22, 0.32, 1))

        # estrellas: una sola malla de puntos sobre una esfera lejana
        rnd = random.Random(3)
        verts, cols = [], []
        paleta = ["#ffffff", "#ffe9a8", "#a8d8ff", "#ffc9c9", "#cfd8ff"]
        for _ in range(1400):
            v = Vec3(rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1)).normalized() * rnd.uniform(260, 420)
            verts.append(v)
            cols.append(rgba(rnd.choice(paleta), rnd.uniform(0.5, 1)))
        self.estrellas = Entity(model=Mesh(vertices=verts, colors=cols, mode="point", thickness=0.03),
                                shader=unlit_shader)

        # nebulosas: manchas difuminadas y translúcidas, muy al fondo
        tex = textura_resplandor()
        # (el fondo cuelga de la cámara para que siempre quede a la vista)
        for x, y, z, esc, hexa, a in [(-120, 45, 300, 300, "#9c27b0", 0.34), (125, 30, 310, 280, "#00acc1", 0.26),
                                      (10, -55, 320, 340, "#651fff", 0.28), (-150, -70, 305, 230, "#0288d1", 0.26),
                                      (160, -75, 300, 210, "#e91e63", 0.18)]:
            Entity(parent=camera, model="quad", texture=tex, position=(x, y, z), scale=esc, color=rgba(hexa, a),
                   shader=unlit_shader)

        # planeta gigante con anillos, luna y planeta lejano
        self.planeta = Entity(parent=camera, model="sphere", position=(100, 42, 220), scale=46,
                              color=rgba("#b06a34"))
        Entity(model=malla_anillo(0.64, 0.92), parent=self.planeta, rotation=(-10, 0, 12), color=rgba("#cbb89f", 0.5),
               double_sided=True, shader=unlit_shader)
        self.luna = Entity(parent=camera, model="sphere", position=(-108, 30, 220), scale=13, color=rgba("#9e9e9e"))
        Entity(parent=camera, model="sphere", position=(-30, 66, 260), scale=8, color=rgba("#4dd0e1"))

        # asteroides que giran alrededor del campo
        self.asteroides = []
        for _ in range(16):
            lado = rnd.choice([-1, 1])
            a = Entity(model="sphere", color=rgba(rnd.choice(["#4a443f", "#5a524a", "#3b3632"])),
                       position=(lado * rnd.uniform(14, 30), rnd.uniform(-6, 5), rnd.uniform(-6, 40)),
                       scale=(rnd.uniform(0.6, 2.0), rnd.uniform(0.5, 1.4), rnd.uniform(0.6, 1.8)),
                       rotation=(rnd.uniform(0, 360), rnd.uniform(0, 360), 0))
            a.giro = Vec3(rnd.uniform(-25, 25), rnd.uniform(-25, 25), rnd.uniform(-25, 25))
            self.asteroides.append(a)

        # rejilla tenue bajo las naves: da referencia de profundidad
        Entity(model=Grid(10, 10), rotation_x=90, y=-1.2, scale=(LIMITE_X * 2 + 2.5, 20, 1),
               color=rgba("#4fc3f7", 0.16), shader=unlit_shader)

    # --- HUD ------------------------------------------------------------------
    def crear_hud(self):
        ui = camera.ui
        x0 = -0.5 * window.aspect_ratio + 0.03
        self.fondos, self.barras, self.nombres = [], [], []
        for i, y in ((0, -0.45), (1, 0.45), (2, -0.41)):
            self.fondos.append(Entity(parent=ui, model="quad", origin=(-0.5, 0), position=(x0, y),
                                      scale=(0.32, 0.022), color=rgba("#20222e")))
            self.barras.append(Entity(parent=ui, model="quad", origin=(-0.5, 0), position=(x0, y, -0.01),
                                      scale=(0.32, 0.022), color=rgba(HEX[i])))
            self.nombres.append(Text(parent=ui, position=(x0 + 0.34, y + 0.013), scale=0.9, color=rgba(HEX[i])))
        self.info = Text(parent=ui, origin=(0, 0), position=(0, -0.475), scale=0.72, color=rgba("#9aa0c0"))
        self.titulo = Text(parent=ui, origin=(0, 0), position=(0, 0.12), scale=3)
        self.subtitulo = Text(parent=ui, origin=(0, 0), position=(0, 0.03), scale=1.1)

    # --- estado ---------------------------------------------------------------
    def reiniciar(self):
        for b in self.balas:
            destroy(b)
        for p in self.particulas:
            destroy(p)
        self.balas, self.particulas = [], []
        equipo = self.modo == EQUIPO
        self.en_juego = (0, 1, 2) if equipo else (0, 1)
        self.vida_max = [VIDA, VIDA * VIDA_PC_EQUIPO if equipo else VIDA, VIDA]
        self.vida = list(self.vida_max)
        self.cd = [0.0, 0.7, 0.0]
        self.objetivo_ia = 0.0
        self.reloj_ia = 0.0
        self.pausa = False
        self.fin = False
        self.ganador = None  # bando ganador (None si hay empate)
        for i, nave in enumerate(self.naves):
            nave.x = (-3.5, 0, 3.5)[i] if equipo else 0
            nave.rotation_z = 0
            nave.enabled = i in self.en_juego
        self.actualizar_hud()

    def cambiar_modo(self):
        self.modo = (self.modo + 1) % len(MODO)
        self.victorias = [0, 0]
        self.reiniciar()

    def input(self, key):
        if key == "r":
            self.reiniciar()
        elif key == "m":
            self.cambiar_modo()
        elif key == "p" and not self.fin:
            self.pausa = not self.pausa
            self.actualizar_hud()
        elif key in ("1", "2", "3"):
            self.nivel = int(key)
            self.actualizar_hud()
        elif key == "escape":
            application.quit()

    # --- lógica ---------------------------------------------------------------
    def disparar(self, i):
        sentido = 1 if BANDO[i] == 0 else -1
        b = Entity(model="cube", scale=(0.14, 0.14, 0.9), color=rgba(HEX_BALA[i]), shader=unlit_shader,
                   position=(self.naves[i].x, 0, Z_NAVE[BANDO[i]] + sentido * 1.4))
        b.vz = sentido * VEL_BALA
        b.dueno = i
        # la IA decide al ver el disparo si lo va a esquivar
        b.esquivable = random.random() < DIFICULTAD[self.nivel][3]
        self.balas.append(b)

    def mover_nave(self, i, direccion, velocidad):
        nave = self.naves[i]
        nave.x = max(-LIMITE_X, min(LIMITE_X, nave.x + direccion * velocidad * time.dt))
        # la nave se inclina hacia donde gira
        giro = -direccion * 28 * (1 if BANDO[i] == 0 else -1)
        nave.rotation_z += (giro - nave.rotation_z) * min(1, 10 * time.dt)

    def mover_humano(self, i, izq, der, disp):
        if self.vida[i] <= 0:
            return
        direccion = (1 if any(held_keys[k] for k in der) else 0) - (1 if any(held_keys[k] for k in izq) else 0)
        self.mover_nave(i, direccion, VEL_NAVE)
        self.cd[i] = max(0.0, self.cd[i] - time.dt)
        if self.cd[i] == 0 and any(held_keys[k] for k in disp):
            self.disparar(i)
            self.cd[i] = ENFRIAMIENTO

    def mover_ia(self):
        _, vel, cd, _, error = DIFICULTAD[self.nivel]
        yo = self.naves[1]
        rivales = [self.naves[i] for i in self.en_juego if BANDO[i] == 0 and self.vida[i] > 0]
        # 1) esquivar la bala rival más cercana
        peligro = None
        for b in self.balas:
            if BANDO[b.dueno] == 0 and b.esquivable and b.z > Z_NAVE[1] - 9 and abs(b.x - yo.x) < 1.7:
                if peligro is None or b.z > peligro.z:
                    peligro = b
        direccion = 0
        if peligro:
            direccion = 1 if yo.x >= peligro.x else -1
            if yo.x < -LIMITE_X + 1.5:
                direccion = 1
            elif yo.x > LIMITE_X - 1.5:
                direccion = -1
        else:
            # 2) apuntar al rival más cercano con algo de error
            self.reloj_ia -= time.dt
            if self.reloj_ia <= 0:
                cerca = min(rivales, key=lambda r: abs(r.x - yo.x))
                self.objetivo_ia = cerca.x + random.uniform(-error, error)
                self.reloj_ia = random.uniform(0.2, 0.6)
            dif = self.objetivo_ia - yo.x
            if abs(dif) > 0.25:
                direccion = 1 if dif > 0 else -1
        self.mover_nave(1, direccion, vel)

        # 3) disparar si está alineada (o de vez en cuando por sorpresa)
        self.cd[1] = max(0.0, self.cd[1] - time.dt)
        alineada = any(abs(yo.x - r.x) < 1.3 for r in rivales)
        if self.cd[1] == 0 and (alineada or random.random() < 0.6 * time.dt):
            self.disparar(1)
            self.cd[1] = cd + random.uniform(0, 0.15)
            if self.modo == EQUIPO:
                self.cd[1] *= CADENCIA_PC_EQUIPO

    def mover_balas(self):
        vivas = []
        for b in self.balas:
            b.z += b.vz * time.dt
            # la bala golpea a cualquier nave viva del bando contrario
            golpe = next((i for i in self.en_juego if BANDO[i] != BANDO[b.dueno] and self.vida[i] > 0
                          and abs(b.x - self.naves[i].x) < 1.15 and abs(b.z - Z_NAVE[BANDO[i]]) < 0.9), None)
            if abs(b.z) > 16:
                destroy(b)
            elif golpe is not None:
                self.vida[golpe] -= 1
                self.explosion(b.position, HEX[golpe], 10)
                camera.shake(duration=0.15, magnitude=0.4)
                if self.vida[golpe] <= 0:
                    self.explosion(self.naves[golpe].position, "#ffd54f", 45, fuerza=9)
                    self.naves[golpe].enabled = False
                destroy(b)
            else:
                vivas.append(b)
        self.balas = vivas
        # un bando pierde cuando no le queda ninguna nave
        vivo = [any(self.vida[i] > 0 for i in self.en_juego if BANDO[i] == bando) for bando in (0, 1)]
        if not all(vivo) and not self.fin:
            self.fin = True
            self.ganador = 0 if vivo[0] else 1 if vivo[1] else None
            if self.ganador is not None:
                self.victorias[self.ganador] += 1
        self.actualizar_hud()

    def explosion(self, pos, hexa, n, fuerza=5.0):
        for _ in range(n):
            p = Entity(model="cube", position=pos, scale=random.uniform(0.08, 0.2), color=rgba(hexa),
                       shader=unlit_shader, rotation=(random.uniform(0, 360), random.uniform(0, 360), 0))
            p.vel = Vec3(random.uniform(-1, 1), random.uniform(-0.3, 1), random.uniform(-1, 1)) * fuerza
            p.vida = random.uniform(0.3, 0.9)
            self.particulas.append(p)

    def mover_efectos(self):
        vivas = []
        for p in self.particulas:
            p.position += p.vel * time.dt
            p.vida -= time.dt
            p.scale *= max(0.0, 1 - 2 * time.dt)
            if p.vida <= 0:
                destroy(p)
            else:
                vivas.append(p)
        self.particulas = vivas
        for nave in self.naves:
            nave.motor.scale = random.uniform(0.3, 0.5)
        for a in self.asteroides:
            a.rotation += a.giro * time.dt
        self.estrellas.rotation_y += 0.6 * time.dt
        self.planeta.rotation_y += 3 * time.dt

    def actualizar_hud(self):
        v = self.victorias
        if self.modo == UNO:
            nombres = (f"TÚ   victorias: {v[0]}", f"COMPUTADOR   victorias: {v[1]}", "")
        elif self.modo == EQUIPO:
            nombres = (f"JUGADOR 1   victorias del equipo: {v[0]}", f"COMPUTADOR   victorias: {v[1]}", "JUGADOR 2")
        else:
            nombres = (f"JUGADOR 1   victorias: {v[0]}", f"JUGADOR 2   victorias: {v[1]}", "")
        for i, nombre in enumerate(nombres):
            self.barras[i].scale_x = 0.32 * max(0, self.vida[i]) / self.vida_max[i]
            self.nombres[i].text = nombre
            self.fondos[i].enabled = self.barras[i].enabled = self.nombres[i].enabled = i in self.en_juego
        modo = MODO[self.modo] + ("" if self.modo == DUELO else f" - {DIFICULTAD[self.nivel][0]} (1/2/3)")
        ayuda = "A/D o Flechas + Espacio" if self.modo == UNO else "J1: A/D + W/Espacio   J2: Flechas + Arriba/Enter"
        self.info.text = f"{modo}   |   {ayuda}   |   M modo   P pausa   R reiniciar"
        self.titulo.text, self.subtitulo.text = "", ""
        if self.fin:
            if self.ganador is None:
                self.titulo.text, self.titulo.color = "EMPATE", rgba("#ffd54f")
            else:
                self.titulo.text = FINAL[self.modo][self.ganador]
                self.titulo.color = rgba(("#a5d6a7", "#ef9a9a")[self.ganador])
            self.subtitulo.text = "Presiona R para jugar de nuevo"
        elif self.pausa:
            self.titulo.text, self.titulo.color = "PAUSA", color.white

    def update(self):
        if self.pausa:
            return
        if not self.fin:
            if self.modo == UNO:
                self.mover_humano(0, *TECLAS_SOLO)
            else:
                self.mover_humano(0, *TECLAS_J1)
                self.mover_humano(2 if self.modo == EQUIPO else 1, *TECLAS_J2)
            if self.modo != DUELO:
                self.mover_ia()
            self.mover_balas()
        self.mover_efectos()


def crear_app():
    app = Ursina(title="Duelo de naves 3D", size=(1200, 720), borderless=False, fullscreen=False,
                 development_mode=False, editor_ui_enabled=False)
    Entity.default_shader = lit_with_shadows_shader
    return app, Juego()


if __name__ == "__main__":
    app, juego = crear_app()
    app.run()
