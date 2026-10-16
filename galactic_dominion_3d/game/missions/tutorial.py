"""Tutorial integrado en la primera misión de la Frontera de Orión.

Cada paso muestra una indicación y avanza cuando el jugador hace lo que se
le pide. Los enemigos no aparecen hasta que se aprende a disparar.
"""
from __future__ import annotations

STEPS = [
    ("Mueve el ratón para apuntar la nave.", "look"),
    ("W acelera y S frena. Mantén Shift para el impulso.", "thrust"),
    ("A/D desplazan la nave; Q/E la hacen girar sobre su eje.", "strafe"),
    ("Clic izquierdo: dispara el cañón de energía.", "fire"),
    ("¡Contactos! Tab fija un objetivo. Mantenlo en la mira y usa el clic derecho para lanzar misiles guiados.",
     "target"),
    ("Espacio: maniobra evasiva (esquiva misiles y rayos). ¡Derriba a los exploradores!", "timer"),
]


class Tutorial:
    def __init__(self, hud):
        self.hud = hud
        self.step = 0
        self.look = 0.0
        self.shots = 0
        self.timer = 0.0
        self.done = False
        self.hud.tutorial(STEPS[0][0])

    @property
    def enemies_allowed(self) -> bool:
        return self.done or self.step >= 4

    def update(self, dt: float, session) -> None:
        if self.done:
            return
        inp = session.last_input
        player = session.player
        kind = STEPS[self.step][1]
        self.timer += dt
        ok = False
        if kind == "look":
            self.look += abs(inp.yaw) + abs(inp.pitch)
            ok = self.look > 45
        elif kind == "thrust":
            ok = player.speed > 62 or player.boosting
        elif kind == "strafe":
            ok = abs(inp.strafe) > 0 or abs(inp.roll) > 0
        elif kind == "fire":
            if inp.fire_primary:
                self.shots += 1
            ok = self.shots > 25
        elif kind == "target":
            ok = session.target is not None and self.timer > 3
        elif kind == "timer":
            ok = self.timer > 7
        if ok and self.timer > 1.2:
            self.step += 1
            self.timer = 0.0
            session.app.audio.play("ui_confirm", 0.5)
            if self.step >= len(STEPS):
                self.done = True
                self.hud.tutorial("")
            else:
                self.hud.tutorial(STEPS[self.step][0])
