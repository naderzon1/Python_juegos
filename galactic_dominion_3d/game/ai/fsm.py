"""Inteligencia artificial de los enemigos: máquina de estados.

Estados: patrulla, persecución, ataque frontal, flanqueo (ataque lateral),
maniobra evasiva, retirada, defensa de un punto y torreta fija. El cerebro
recibe una ``Perception`` (lo que la nave "ve") y devuelve un ``Command``
(rumbo deseado, potencia y si dispara). No mueve nada por sí mismo: así la
lógica se puede probar sin abrir una ventana.

Coordinación: un ``SquadCoordinator`` reparte "turnos de ataque". Las naves
sin turno mantienen la distancia flanqueando, de modo que el jugador no
recibe a toda la flota a la vez y los ataques llegan por oleadas y lados.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from panda3d.core import Vec3

PATROL, CHASE, ATTACK, FLANK, EVADE, RETREAT, DEFEND, TURRET = (
    "patrulla", "persecución", "ataque", "flanqueo", "evasión", "retirada", "defensa", "torreta")


@dataclass
class Perception:
    pos: Vec3
    forward: Vec3
    hull_ratio: float
    target_pos: Vec3 | None
    target_vel: Vec3
    target_forward: Vec3
    projectile_speed: float
    weapon_range: float
    under_fire: bool = False
    may_attack: bool = True
    defend_point: Vec3 | None = None
    dt: float = 0.016


@dataclass
class Command:
    direction: Vec3
    throttle: float
    fire: bool = False
    fire_missile: bool = False
    aim_point: Vec3 | None = None


def _norm(v: Vec3) -> Vec3:
    length = v.length()
    return Vec3(v) / length if length > 1e-6 else Vec3(0, 1, 0)


def angle_between(a: Vec3, b: Vec3) -> float:
    dot = max(-1.0, min(1.0, _norm(a).dot(_norm(b))))
    return math.degrees(math.acos(dot))


def lead_point(shooter: Vec3, target: Vec3, target_vel: Vec3, speed: float, skill: float = 1.0) -> Vec3:
    if speed <= 0:
        return Vec3(target)
    t = (target - shooter).length() / speed
    return target + target_vel * t * skill


class Brain:
    def __init__(self, ai_cfg: dict, rng: random.Random | None = None, static: bool = False, side: int = 1):
        self.cfg = ai_cfg
        self.rng = rng or random.Random()
        self.state = TURRET if static else CHASE
        self.static = static
        self.side = side
        self.timer = 0.0
        self.evade_dir = Vec3(1, 0, 0)
        self.retreated = False
        self.patrol_center: Vec3 | None = None
        self.patrol_goal: Vec3 | None = None
        self.missile_timer = self.rng.uniform(3, 7)
        accuracy = float(ai_cfg.get("accuracy", 0.6))
        self.fire_cone = 3.0 + (1.0 - accuracy) * 9.0

    def set_state(self, state: str, duration: float = 0.0) -> None:
        self.state = state
        self.timer = duration

    def start_patrol(self, center: Vec3) -> None:
        self.patrol_center = Vec3(center)
        self.set_state(PATROL)

    # ---------------------------------------------------------------------
    def update(self, p: Perception) -> Command:
        cfg = self.cfg
        self.timer -= p.dt
        self.missile_timer -= p.dt
        if p.target_pos is None:
            return self._patrol(p)
        to_target = p.target_pos - p.pos
        dist = to_target.length()
        preferred = float(cfg.get("preferred_range", 350))
        if self.static:
            cmd = self._attack_command(p, dist, throttle=0.0, direction=_norm(to_target))
            cmd.fire = dist < p.weapon_range  # las torretas giran: no dependen del rumbo del casco
            return cmd

        # transiciones globales
        if (not self.retreated and p.hull_ratio < float(cfg.get("retreat_hp", 0))
                and self.state not in (RETREAT, EVADE)):
            self.retreated = True
            self.set_state(RETREAT, self.rng.uniform(4.0, 6.0))
        if p.defend_point is not None and self.state not in (RETREAT, DEFEND):
            if (p.target_pos - p.defend_point).length() > 900:
                self.set_state(DEFEND)
        if self.state == PATROL:
            if dist < float(cfg.get("detect_range", 1400)) or p.under_fire:
                self.set_state(CHASE)
            else:
                return self._patrol(p)

        if self.state == DEFEND:
            if p.defend_point is None or (p.target_pos - p.defend_point).length() < 700:
                self.set_state(CHASE)
            else:
                to_point = p.defend_point - p.pos
                return Command(_norm(to_point), 0.8 if to_point.length() > 150 else 0.3)

        if self.state == RETREAT:
            if self.timer <= 0:
                self.set_state(CHASE)
            else:
                away = _norm(-to_target + self.evade_dir * 0.4)
                return Command(away, 1.15)

        if self.state == EVADE:
            if self.timer <= 0:
                self.set_state(CHASE)
            else:
                return Command(_norm(self.evade_dir + _norm(to_target) * 0.25), 1.2)

        # ¿esquivar? si el objetivo nos apunta y estamos recibiendo fuego
        aimed_at_me = angle_between(p.target_forward, p.pos - p.target_pos) < 9 and dist < 900
        if (p.under_fire or aimed_at_me) and self.state in (ATTACK, CHASE, FLANK):
            chance = float(cfg.get("evade_chance", 0.3)) * p.dt * 1.6
            if self.rng.random() < chance:
                return self._begin_evade(to_target)

        if self.state == CHASE:
            if dist < preferred * 1.7:
                if not p.may_attack or (cfg.get("flank") and self.rng.random() < 0.45):
                    self.set_state(FLANK, self.rng.uniform(2.5, 4.5))
                else:
                    self.set_state(ATTACK, self.rng.uniform(4, 7))
            aim = lead_point(p.pos, p.target_pos, p.target_vel, p.projectile_speed, 0.8)
            return self._attack_command(p, dist, throttle=1.0, direction=_norm(aim - p.pos))

        if self.state == FLANK:
            if self.timer <= 0 and p.may_attack:
                self.set_state(ATTACK, self.rng.uniform(4, 7))
            orbit = preferred * (1.0 if p.may_attack else 1.6)
            radial = _norm(-to_target)
            tangent = _norm(radial.cross(Vec3(0, 0, 1)) * self.side)
            correction = (dist - orbit) / max(orbit, 1.0)
            direction = _norm(tangent + _norm(to_target) * correction * 1.5)
            return self._attack_command(p, dist, throttle=0.95, direction=direction)

        if self.state == ATTACK:
            if dist < preferred * 0.45:
                # demasiado cerca: rompe el ataque y pasa de largo
                return self._begin_evade(to_target, duration=self.rng.uniform(1.0, 1.6))
            if self.timer <= 0 or not p.may_attack:
                self.set_state(FLANK, self.rng.uniform(2.0, 4.0))
            aim = lead_point(p.pos, p.target_pos, p.target_vel, p.projectile_speed,
                             float(cfg.get("accuracy", 0.6)))
            throttle = 1.0 if dist > preferred else 0.6
            return self._attack_command(p, dist, throttle=throttle, direction=_norm(aim - p.pos))

        return Command(_norm(to_target), 1.0)

    # ---------------------------------------------------------------------
    def _begin_evade(self, to_target: Vec3, duration: float | None = None) -> Command:
        perp = _norm(to_target).cross(Vec3(self.rng.uniform(-1, 1), self.rng.uniform(-1, 1),
                                           self.rng.uniform(-1, 1)))
        self.evade_dir = _norm(perp if perp.length() > 0.1 else Vec3(1, 0, 0))
        self.set_state(EVADE, duration or self.rng.uniform(1.0, 1.8))
        return Command(self.evade_dir, 1.2)

    def _attack_command(self, p: Perception, dist: float, throttle: float, direction: Vec3) -> Command:
        aim = lead_point(p.pos, p.target_pos, p.target_vel, p.projectile_speed,
                         float(self.cfg.get("accuracy", 0.6)))
        in_cone = angle_between(p.forward, aim - p.pos) < self.fire_cone
        fire = in_cone and dist < p.weapon_range
        fire_missile = False
        if self.cfg.get("missiles") and self.missile_timer <= 0 and 180 < dist < 1400:
            fire_missile = True
            self.missile_timer = self.rng.uniform(5.0, 9.0)
        return Command(direction, throttle, fire=fire, fire_missile=fire_missile, aim_point=aim)

    def _patrol(self, p: Perception) -> Command:
        center = self.patrol_center or p.pos
        if self.patrol_goal is None or (self.patrol_goal - p.pos).length() < 60:
            self.patrol_goal = center + Vec3(self.rng.uniform(-300, 300), self.rng.uniform(-300, 300),
                                             self.rng.uniform(-80, 80))
        return Command(_norm(self.patrol_goal - p.pos), 0.45)


class SquadCoordinator:
    """Reparte turnos de ataque para que los enemigos coordinen sus pasadas."""

    def __init__(self, max_attackers: int = 3, rotate_every: float = 6.0):
        self.max_attackers = max_attackers
        self.rotate_every = rotate_every
        self.timer = rotate_every
        self.attackers: list = []

    def update(self, dt: float, members: list) -> None:
        alive = [m for m in members if m.alive]
        self.attackers = [m for m in self.attackers if m in alive]
        self.timer -= dt
        if self.timer <= 0:
            self.timer = self.rotate_every
            if self.attackers:
                self.attackers.pop(0)
        for member in alive:
            if len(self.attackers) >= self.max_attackers:
                break
            if member not in self.attackers:
                self.attackers.append(member)

    def may_attack(self, member) -> bool:
        return member in self.attackers
