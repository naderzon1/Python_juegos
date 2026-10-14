"""Pong: Usuario vs Computador.

Controles:
  W / S o flechas arriba / abajo  -> mover tu paleta (izquierda)
  ESPACIO                         -> pausa
  R                               -> reiniciar
  1 / 2 / 3                       -> dificultad (fácil / media / difícil)
El primero en llegar a 7 puntos gana.
"""
import random
import tkinter as tk

ANCHO, ALTO = 800, 500
PALETA_W, PALETA_H = 12, 90
BOLA = 14
FPS_MS = 16
META = 7
VEL_USUARIO = 8

# dificultad: (velocidad máxima de la IA, error de puntería en px)
DIFICULTAD = {1: ("Fácil", 3.5, 45), 2: ("Media", 5.5, 25), 3: ("Difícil", 7.5, 8)}


class Pong:
    def __init__(self, root):
        self.root = root
        root.title("Pong - Usuario vs Computador")
        root.resizable(False, False)
        self.c = tk.Canvas(root, width=ANCHO, height=ALTO, bg="#101820", highlightthickness=0)
        self.c.pack()
        self.teclas = set()
        root.bind("<KeyPress>", lambda e: self.teclas.add(e.keysym.lower()))
        root.bind("<KeyRelease>", lambda e: self.teclas.discard(e.keysym.lower()))
        root.bind("<space>", lambda e: self.pausar())
        root.bind("r", lambda e: self.reiniciar())
        for n in DIFICULTAD:
            root.bind(str(n), lambda e, n=n: self.set_dificultad(n))
        self.nivel = 2
        self.reiniciar()
        self.bucle()

    def set_dificultad(self, n):
        self.nivel = n

    def reiniciar(self):
        self.y_user = self.y_ia = (ALTO - PALETA_H) / 2
        self.p_user = self.p_ia = 0
        self.pausa = False
        self.fin = False
        self.sacar(random.choice([-1, 1]))

    def sacar(self, direccion):
        self.bx, self.by = ANCHO / 2, ALTO / 2
        self.vx = 5.0 * direccion
        self.vy = random.choice([-1, 1]) * random.uniform(2, 4)
        self.objetivo_ia = ALTO / 2
        self.espera = 40  # frames de pausa antes de mover la bola

    def pausar(self):
        if not self.fin:
            self.pausa = not self.pausa

    def mover_usuario(self):
        if "w" in self.teclas or "up" in self.teclas:
            self.y_user -= VEL_USUARIO
        if "s" in self.teclas or "down" in self.teclas:
            self.y_user += VEL_USUARIO
        self.y_user = max(0, min(ALTO - PALETA_H, self.y_user))

    def mover_ia(self):
        _, vmax, error = DIFICULTAD[self.nivel]
        # Solo reacciona cuando la bola viene hacia ella; si no, vuelve al centro.
        if self.vx > 0:
            if random.random() < 0.05:  # recalcula puntería con error humano
                self.objetivo_ia = self.by + random.uniform(-error, error)
            centro = self.y_ia + PALETA_H / 2
        else:
            self.objetivo_ia = ALTO / 2
            centro = self.y_ia + PALETA_H / 2
        dif = self.objetivo_ia - centro
        paso = max(-vmax, min(vmax, dif))
        if abs(dif) > 4:
            self.y_ia += paso
        self.y_ia = max(0, min(ALTO - PALETA_H, self.y_ia))

    def mover_bola(self):
        if self.espera > 0:
            self.espera -= 1
            return
        self.bx += self.vx
        self.by += self.vy
        if self.by <= 0 or self.by + BOLA >= ALTO:
            self.vy = -self.vy
            self.by = max(0, min(ALTO - BOLA, self.by))

        # Paleta del usuario (x=20)
        if self.vx < 0 and 20 <= self.bx <= 20 + PALETA_W and self.y_user - BOLA <= self.by <= self.y_user + PALETA_H:
            self.rebote(self.y_user, 20 + PALETA_W, 1)
        # Paleta de la IA
        xi = ANCHO - 20 - PALETA_W
        if self.vx > 0 and xi - BOLA <= self.bx <= xi and self.y_ia - BOLA <= self.by <= self.y_ia + PALETA_H:
            self.rebote(self.y_ia, xi - BOLA, -1)

        if self.bx < -BOLA:
            self.p_ia += 1
            self.punto(-1)
        elif self.bx > ANCHO:
            self.p_user += 1
            self.punto(1)

    def rebote(self, y_paleta, x_nueva, signo):
        self.bx = x_nueva
        # El punto de impacto en la paleta define el ángulo
        rel = (self.by + BOLA / 2 - (y_paleta + PALETA_H / 2)) / (PALETA_H / 2)
        rel = max(-1, min(1, rel))
        vel = min(abs(self.vx) * 1.06, 13)
        self.vx = signo * vel
        self.vy = rel * 6

    def punto(self, direccion):
        if self.p_user >= META or self.p_ia >= META:
            self.fin = True
        else:
            self.sacar(direccion)

    def dibujar(self):
        c = self.c
        c.delete("all")
        for y in range(0, ALTO, 30):
            c.create_rectangle(ANCHO / 2 - 2, y, ANCHO / 2 + 2, y + 16, fill="#2a3a4a", width=0)
        c.create_rectangle(20, self.y_user, 20 + PALETA_W, self.y_user + PALETA_H, fill="#4fc3f7", width=0)
        xi = ANCHO - 20 - PALETA_W
        c.create_rectangle(xi, self.y_ia, xi + PALETA_W, self.y_ia + PALETA_H, fill="#ff7043", width=0)
        c.create_oval(self.bx, self.by, self.bx + BOLA, self.by + BOLA, fill="white", width=0)
        fuente = ("Consolas", 36, "bold")
        c.create_text(ANCHO / 2 - 60, 40, text=str(self.p_user), fill="#4fc3f7", font=fuente)
        c.create_text(ANCHO / 2 + 60, 40, text=str(self.p_ia), fill="#ff7043", font=fuente)
        c.create_text(70, ALTO - 15, text="TÚ", fill="#4fc3f7", font=("Consolas", 11))
        c.create_text(ANCHO - 90, ALTO - 15, text="COMPUTADOR", fill="#ff7043", font=("Consolas", 11))
        c.create_text(ANCHO / 2, ALTO - 15, fill="#8899aa", font=("Consolas", 10),
                      text=f"Dificultad: {DIFICULTAD[self.nivel][0]} (1/2/3) | Espacio: pausa | R: reiniciar")
        if self.fin:
            gano = self.p_user > self.p_ia
            c.create_text(ANCHO / 2, ALTO / 2 - 10, font=("Consolas", 34, "bold"),
                          text="¡GANASTE!" if gano else "GANÓ EL COMPUTADOR",
                          fill="#a5d6a7" if gano else "#ef9a9a")
            c.create_text(ANCHO / 2, ALTO / 2 + 40, text="Presiona R para jugar de nuevo",
                          fill="white", font=("Consolas", 14))
        elif self.pausa:
            c.create_text(ANCHO / 2, ALTO / 2, text="PAUSA", fill="white", font=("Consolas", 34, "bold"))

    def bucle(self):
        if not self.pausa and not self.fin:
            self.mover_usuario()
            self.mover_ia()
            self.mover_bola()
        self.dibujar()
        self.root.after(FPS_MS, self.bucle)


if __name__ == "__main__":
    root = tk.Tk()
    Pong(root)
    root.mainloop()
