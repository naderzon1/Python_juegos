"""Duelo de naves en el espacio, con tres modos de juego:

  PC vs USUARIO       -> tú contra el computador
  PC vs 2 USUARIOS    -> dos jugadores en equipo contra el computador
  USUARIO vs USUARIO  -> un jugador contra el otro

Controles:
  JUGADOR 1 (azul)  : A / D mover,  W o ESPACIO disparar
  JUGADOR 2         : flechas ← / → mover,  ↑ o ENTER disparar
                      (verde y abajo si juega en equipo; naranja y arriba si es el rival)
  (en PC vs USUARIO también puedes mover con las flechas ← / →)
  M          -> cambiar modo
  1 / 2 / 3  -> dificultad del computador (fácil / media / difícil)
  P pausa  |  R reiniciar partida
Gana el bando que deje al otro sin vida.
"""
import random
import tkinter as tk

ANCHO, ALTO = 700, 600
NAVE_W, NAVE_H = 44, 30
VIDA = 10
FPS_MS = 16
VEL_NAVE = 7
VEL_BALA = 9
ENFRIAMIENTO = 15  # frames entre disparos humanos
Y_NAVE = (ALTO - 45, 45)  # bando 0 abajo, bando 1 arriba

# modos de juego: M los recorre en este orden
UNO, EQUIPO, DUELO = 0, 1, 2
MODO = ("PC vs USUARIO", "PC vs 2 USUARIOS", "USUARIO vs USUARIO")
NOMBRES = (("TÚ", "COMPUTADOR"), ("JUGADOR 1 + JUGADOR 2", "COMPUTADOR"), ("JUGADOR 1", "JUGADOR 2"))
FINAL = (("¡VICTORIA!", "DERROTA"), ("¡GANA EL EQUIPO!", "GANÓ EL COMPUTADOR"), ("¡GANA JUGADOR 1!", "¡GANA JUGADOR 2!"))

# nave 0: jugador 1 | nave 1: computador o jugador 2 rival | nave 2: jugador 2 aliado (solo en equipo)
BANDO = (0, 1, 0)
COLOR = ("#4fc3f7", "#ff7043", "#81c784")
COLOR_BALA = ("#80d8ff", "#ffab91", "#c8e6c9")
TECLAS_SOLO = ({"a", "left"}, {"d", "right"}, {"w", "space"})
TECLAS_J1 = ({"a"}, {"d"}, {"w", "space"})
TECLAS_J2 = ({"left"}, {"right"}, {"up", "return"})

# contra dos jugadores el computador tiene el doble de vida y dispara más seguido
VIDA_PC_EQUIPO = 2
CADENCIA_PC_EQUIPO = 0.7

# nombre, velocidad nave IA, enfriamiento de disparo IA, esquiva (0-1), error de puntería px
DIFICULTAD = {1: ("Fácil", 3.0, 55, 0.3, 60), 2: ("Media", 4.5, 38, 0.7, 30), 3: ("Difícil", 6.0, 26, 0.95, 10)}


class Naves:
    def __init__(self, root):
        self.root = root
        root.title("Duelo de naves - Espacio exterior")
        root.resizable(False, False)
        self.c = tk.Canvas(root, width=ANCHO, height=ALTO, bg="#05060f", highlightthickness=0)
        self.c.pack()
        self.estrellas = [[random.randint(0, ANCHO), random.randint(0, ALTO), random.choice([1, 1, 1, 2, 2, 3]),
                           random.choice(["#445", "#889", "#ccd", "#fff", "#ffe9a8", "#a8d8ff"])]
                          for _ in range(130)]
        self.modo = UNO
        self.nivel = 2
        self.victorias = [0, 0]  # por bando
        self.dibujar_fondo()
        self.teclas = set()
        root.bind("<KeyPress>", lambda e: self.teclas.add(e.keysym.lower()))
        root.bind("<KeyRelease>", lambda e: self.teclas.discard(e.keysym.lower()))
        root.bind("p", lambda e: self.pausar())
        root.bind("r", lambda e: self.reiniciar())
        root.bind("m", lambda e: self.cambiar_modo())
        for n in DIFICULTAD:
            root.bind(str(n), lambda e, n=n: self.set_dificultad(n))
        self.reiniciar()
        self.bucle()

    # --- estado -----------------------------------------------------------
    def set_dificultad(self, n):
        self.nivel = n

    def cambiar_modo(self):
        self.modo = (self.modo + 1) % len(MODO)
        self.victorias = [0, 0]
        self.reiniciar()

    def reiniciar(self):
        equipo = self.modo == EQUIPO
        self.naves = (0, 1, 2) if equipo else (0, 1)  # naves en juego
        self.x = [ANCHO / 3 if equipo else ANCHO / 2, ANCHO / 2, ANCHO * 2 / 3]
        self.vida_max = [VIDA, VIDA * VIDA_PC_EQUIPO if equipo else VIDA, VIDA]
        self.vida = list(self.vida_max)
        self.cd = [0, 40, 0]
        self.balas = []        # [x, y, vy, nave que disparó]
        self.particulas = []   # [x, y, vx, vy, vida, color]
        self.objetivo_ia = ANCHO / 2
        self.pausa = False
        self.fin = False
        self.ganador = None    # bando ganador (None si hay empate)

    def pausar(self):
        if not self.fin:
            self.pausa = not self.pausa

    # --- fondo estático: espacio exterior -----------------------------------
    def dibujar_fondo(self):
        c = self.c
        # degradado del vacío del espacio
        bandas = 30
        for i in range(bandas):
            t = i / (bandas - 1)
            r, g, b = int(4 + 14 * t), int(5 + 4 * t), int(16 + 26 * t)
            c.create_rectangle(0, i * ALTO / bandas, ANCHO, (i + 1) * ALTO / bandas + 1,
                               fill=f"#{r:02x}{g:02x}{b:02x}", width=0, tags="bg")
        # nebulosas: capas concéntricas mezcladas con el fondo (sin transparencia real)
        def mezcla(col, t):
            r, g, b = (int(col[i:i + 2], 16) for i in (1, 3, 5))
            return f"#{int(10 + (r - 10) * t):02x}{int(10 + (g - 10) * t):02x}{int(22 + (b - 22) * t):02x}"
        for x, y, rx, ry, col in [(130, 170, 190, 90, "#9c27b0"), (570, 110, 170, 70, "#00acc1"),
                                  (380, 470, 230, 90, "#651fff"), (90, 520, 160, 60, "#0288d1")]:
            for k in range(6):
                f = 1 - k * 0.16
                c.create_oval(x - rx * f, y - ry * f, x + rx * f, y + ry * f,
                              fill=mezcla(col, 0.08 + k * 0.045), width=0, tags="bg")
        # planeta gigante con anillos
        px, py, pr = 580, 450, 55
        c.create_arc(px - 105, py - 20, px + 105, py + 20, start=0, extent=180, style="arc",
                     outline="#6f6152", width=5, tags="bg")
        c.create_oval(px - pr, py - pr, px + pr, py + pr, fill="#6e3a1c", outline="", tags="bg")
        c.create_oval(px - pr + 4, py - pr + 3, px + pr - 14, py + pr - 12, fill="#a65d2e", outline="", tags="bg")
        c.create_oval(px - pr + 10, py - pr + 8, px + pr - 30, py + pr - 28, fill="#d38a4b", outline="", tags="bg")
        c.create_arc(px - 105, py - 20, px + 105, py + 20, start=180, extent=180, style="arc",
                     outline="#b8a48e", width=5, tags="bg")
        # luna y planeta lejano (cuerpo oscuro + zona iluminada)
        c.create_oval(40, 410, 84, 454, fill="#4a4a4a", outline="", tags="bg")
        c.create_oval(43, 413, 74, 444, fill="#9e9e9e", outline="", tags="bg")
        c.create_oval(52, 424, 60, 432, fill="#757575", outline="", tags="bg")
        c.create_oval(320, 60, 348, 88, fill="#006978", outline="", tags="bg")
        c.create_oval(322, 62, 342, 82, fill="#4dd0e1", outline="", tags="bg")
        # asteroides decorativos
        rnd = random.Random(7)
        for _ in range(9):
            ax, ay, ar = rnd.randint(120, 460), rnd.randint(330, 430), rnd.randint(3, 7)
            c.create_oval(ax - ar, ay - ar * 0.8, ax + ar, ay + ar * 0.8, fill="#5d5650", outline="", tags="bg")

    # --- lógica -----------------------------------------------------------
    def disparar(self, i):
        d = -1 if BANDO[i] == 0 else 1
        self.balas.append([self.x[i], Y_NAVE[BANDO[i]] + d * 15, d * VEL_BALA, i])

    def mover_humano(self, i, izq, der, disp):
        if self.vida[i] <= 0:
            return
        if izq & self.teclas:
            self.x[i] -= VEL_NAVE
        if der & self.teclas:
            self.x[i] += VEL_NAVE
        self.x[i] = max(NAVE_W / 2, min(ANCHO - NAVE_W / 2, self.x[i]))
        self.cd[i] = max(0, self.cd[i] - 1)
        if disp & self.teclas and self.cd[i] == 0:
            self.disparar(i)
            self.cd[i] = ENFRIAMIENTO

    def mover_ia(self):
        _, vel, cd, esquiva, error = DIFICULTAD[self.nivel]
        rivales = [i for i in self.naves if BANDO[i] == 0 and self.vida[i] > 0]
        # 1) esquivar la bala rival más cercana
        peligro = None
        for b in self.balas:
            if BANDO[b[3]] == 0 and b[1] < 260 and abs(b[0] - self.x[1]) < NAVE_W:
                if peligro is None or b[1] < peligro[1]:
                    peligro = b
        if peligro and random.random() < esquiva:
            hacia = 1 if self.x[1] >= peligro[0] else -1
            if self.x[1] < NAVE_W:
                hacia = 1
            elif self.x[1] > ANCHO - NAVE_W:
                hacia = -1
            self.x[1] += hacia * vel
        else:
            # 2) apuntar al rival más cercano con algo de error
            if random.random() < 0.03:
                cerca = min(rivales, key=lambda i: abs(self.x[i] - self.x[1]))
                self.objetivo_ia = self.x[cerca] + random.uniform(-error, error)
            dif = self.objetivo_ia - self.x[1]
            if abs(dif) > 4:
                self.x[1] += max(-vel, min(vel, dif))
        self.x[1] = max(NAVE_W / 2, min(ANCHO - NAVE_W / 2, self.x[1]))

        # 3) disparar si está alineada (o de vez en cuando por sorpresa)
        self.cd[1] = max(0, self.cd[1] - 1)
        alineada = any(abs(self.x[1] - self.x[i]) < NAVE_W * 0.7 for i in rivales)
        if self.cd[1] == 0 and (alineada or random.random() < 0.01):
            self.disparar(1)
            self.cd[1] = cd + random.randint(0, 10)
            if self.modo == EQUIPO:
                self.cd[1] = int(self.cd[1] * CADENCIA_PC_EQUIPO)

    def mover_balas(self):
        vivas = []
        for b in self.balas:
            b[1] += b[2]
            if b[1] < -10 or b[1] > ALTO + 10:
                continue
            # la bala golpea a cualquier nave viva del bando contrario
            golpe = next((i for i in self.naves if BANDO[i] != BANDO[b[3]] and self.vida[i] > 0
                          and abs(b[0] - self.x[i]) < NAVE_W / 2
                          and abs(b[1] - Y_NAVE[BANDO[i]]) < NAVE_H / 2 + 4), None)
            if golpe is not None:
                self.vida[golpe] -= 1
                self.explosion(b[0], b[1], COLOR[golpe], 8)
                if self.vida[golpe] <= 0:
                    self.explosion(self.x[golpe], Y_NAVE[BANDO[golpe]], "#ffd54f", 50)
                continue
            vivas.append(b)
        self.balas = vivas
        # un bando pierde cuando no le queda ninguna nave
        vivo = [any(self.vida[i] > 0 for i in self.naves if BANDO[i] == bando) for bando in (0, 1)]
        if not all(vivo):
            self.fin = True
            self.ganador = 0 if vivo[0] else 1 if vivo[1] else None
            if self.ganador is not None:
                self.victorias[self.ganador] += 1

    def explosion(self, x, y, color, n):
        for _ in range(n):
            self.particulas.append([x, y, random.uniform(-3, 3), random.uniform(-3, 3),
                                    random.randint(10, 30), color])

    def mover_efectos(self):
        for p in self.particulas:
            p[0] += p[2]
            p[1] += p[3]
            p[4] -= 1
        self.particulas = [p for p in self.particulas if p[4] > 0]
        for s in self.estrellas:
            s[1] += s[2] * 0.5
            if s[1] > ALTO:
                s[0], s[1] = random.randint(0, ANCHO), 0

    # --- dibujo -----------------------------------------------------------
    def barra(self, x, y, i):
        """Barra de vida de la nave i: un segmento por punto de vida."""
        for k in range(self.vida_max[i]):
            self.c.create_rectangle(x + k * 14, y, x + k * 14 + 11, y + 10,
                                    fill=COLOR[i] if k < self.vida[i] else "#2a2a3a", width=0, tags="dyn")

    def dibujar(self):
        c = self.c
        c.delete("dyn")
        for x, y, v, col in self.estrellas:
            c.create_rectangle(x, y, x + v, y + v, fill=col, width=0, tags="dyn")

        for i in self.naves:
            if self.vida[i] <= 0:
                continue
            x, y, d = self.x[i], Y_NAVE[BANDO[i]], (-1 if BANDO[i] == 0 else 1)  # d: hacia dónde mira la nave
            # llama del motor
            c.create_polygon(x - 8, y - d * 14, x + 8, y - d * 14, x, y - d * random.randint(24, 32),
                             fill="#ffd54f", outline="", tags="dyn")
            # alas y cuerpo
            c.create_polygon(x, y + d * NAVE_H / 2, x - NAVE_W / 2, y - d * NAVE_H / 2,
                             x + NAVE_W / 2, y - d * NAVE_H / 2, fill=COLOR[i], outline="white", tags="dyn")
            c.create_oval(x - 5, y - 6, x + 5, y + 6, fill="white", width=0, tags="dyn")

        for x, y, vy, dueno in self.balas:
            c.create_rectangle(x - 2, y - 7, x + 2, y + 7, fill=COLOR_BALA[dueno], width=0, tags="dyn")
        for x, y, _, _, vida, col in self.particulas:
            c.create_oval(x - 2, y - 2, x + 2, y + 2, fill=col, width=0, tags="dyn")

        # barras de vida
        self.barra(15, 12, 1)
        self.barra(15, ALTO - 22, 0)
        if self.modo == EQUIPO:
            self.barra(15 + (VIDA + 1) * 14, ALTO - 22, 2)
        n1, n2 = NOMBRES[self.modo]
        c.create_text(ANCHO - 15, 17, anchor="e", fill=COLOR[1], font=("Consolas", 10), tags="dyn",
                      text=f"{n2}  [{self.victorias[1]}]")
        c.create_text(ANCHO - 15, ALTO - 17, anchor="e", fill=COLOR[0], font=("Consolas", 10), tags="dyn",
                      text=f"{n1}  [{self.victorias[0]}]")
        modo = MODO[self.modo] + ("" if self.modo == DUELO else f" - {DIFICULTAD[self.nivel][0]} (1/2/3)")
        c.create_text(ANCHO / 2, ALTO / 2 - 8, fill="#8a8fb0", font=("Consolas", 10), tags="dyn",
                      text=f"Modo: {modo}   |   M: cambiar modo")
        ayuda = ("A/D o ←/→ mover  |  Espacio disparar" if self.modo == UNO
                 else "J1: A/D + W/Espacio   J2: ←/→ + ↑/Enter")
        c.create_text(ANCHO / 2, ALTO / 2 + 10, fill="#6a6f90", font=("Consolas", 9), tags="dyn",
                      text=f"{ayuda}   |   P: pausa   R: reiniciar")

        if self.fin:
            if self.ganador is None:
                txt, col = "EMPATE", "#ffd54f"
            else:
                txt, col = FINAL[self.modo][self.ganador], ("#a5d6a7", "#ef9a9a")[self.ganador]
            c.create_text(ANCHO / 2, ALTO / 2 - 70, text=txt, fill=col, font=("Consolas", 34, "bold"), tags="dyn")
            c.create_text(ANCHO / 2, ALTO / 2 - 35, text="Presiona R para jugar de nuevo",
                          fill="white", font=("Consolas", 13), tags="dyn")
        elif self.pausa:
            c.create_text(ANCHO / 2, ALTO / 2 - 60, text="PAUSA", fill="white",
                          font=("Consolas", 34, "bold"), tags="dyn")

    def bucle(self):
        if not self.pausa:
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
        self.dibujar()
        self.root.after(FPS_MS, self.bucle)


if __name__ == "__main__":
    root = tk.Tk()
    Naves(root)
    root.mainloop()
