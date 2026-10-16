"""Mundo de combate: registro de entidades y reglas de daño compartidas.

Conecta proyectiles, rayos, explosiones de área y destrucción con los
efectos visuales, el audio y la sesión de vuelo (que recibe los avisos de
destrucción para las misiones y las recompensas).
"""
from __future__ import annotations

import math
import random

from panda3d.core import Point3, Vec3

from game.combat.damage import DamageInfo, roll_damage


def segment_sphere(p0: Point3, p1: Point3, center: Point3, radius: float) -> float | None:
    """Devuelve t∈[0,1] del primer punto del segmento dentro de la esfera, o None."""
    d = p1 - p0
    f = p0 - center
    a = d.dot(d)
    if a < 1e-9:
        return 0.0 if f.length() <= radius else None
    b = 2 * f.dot(d)
    c = f.dot(f) - radius * radius
    if c <= 0:
        return 0.0
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    t = (-b - math.sqrt(disc)) / (2 * a)
    return t if 0.0 <= t <= 1.0 else None


class CombatWorld:
    def __init__(self, base, config, effects, audio, rng: random.Random | None = None):
        self.base = base
        self.render = base.render
        self.config = config
        self.effects = effects
        self.audio = audio
        self.rng = rng or random.Random()
        self.entities: list = []
        self.time = 0.0
        self.camera_pos = Point3(0, 0, 0)
        self.listeners: list = []          # funciones on_destroyed(entity, killer)
        self.hit_listeners: list = []      # funciones on_hit(target, source, result)
        self.crit_mult = config.crit_multiplier
        self.difficulty = {"hp_mult": 1.0, "damage_mult": 1.0}

    def add(self, entity) -> None:
        self.entities.append(entity)

    def hostiles_of(self, faction: str) -> list:
        return [e for e in self.entities if e.alive and e.faction != faction and e.targetable]

    def allies_of(self, faction: str) -> list:
        return [e for e in self.entities if e.alive and e.faction == faction]

    def cleanup(self) -> None:
        self.entities = [e for e in self.entities if e.alive]

    # --- daño ---------------------------------------------------------------
    def damage(self, target, wdef, source, point: Point3 | None, mult: float = 1.0, crit_bonus: float = 0.0,
               amount: float | None = None):
        base = wdef.damage if amount is None else amount
        if source is not None and getattr(source, "faction", "") == "enemy":
            mult *= self.difficulty["damage_mult"]
        value, crit = roll_damage(base, mult, wdef.crit_chance + crit_bonus, self.crit_mult, self.rng)
        info = DamageInfo(value, wdef.shield_mult, wdef.hull_mult, crit, source)
        result = target.apply_damage(info, point)
        if point is not None:
            if result.shield_damage > 0 and result.hull_damage <= 0:
                self.audio.play("shield_hit", 0.6, point)
            elif result.hull_damage > 0:
                self.effects.sparks(point, wdef.color, 5)
                self.audio.play("impact", 0.7, point)
        if result.shield_broken:
            self.audio.play("shield_down", 0.6, point or target.pos)
        for listener in self.hit_listeners:
            listener(target, source, result)
        return result

    def area_damage(self, center: Point3, radius: float, wdef, source, mult: float = 1.0,
                    crit_bonus: float = 0.0, faction: str = "player") -> int:
        hits = 0
        for target in self.hostiles_of(faction):
            dist = (target.pos - center).length() - target.bound_radius * 0.5
            if dist < radius:
                falloff = 1.0 - max(0.0, dist) / radius * 0.6
                self.damage(target, wdef, source, None, mult * falloff, crit_bonus)
                hits += 1
        return hits

    def raycast(self, origin: Point3, direction: Vec3, max_dist: float, faction: str):
        """Primer enemigo de ``faction`` que corta el rayo: (entidad, punto, distancia).

        Un punto débil del jefe gana a su casco si está a menos de 40 m del primer impacto.
        """
        end = origin + direction * max_dist
        hits = []
        for target in self.hostiles_of(faction):
            to_c = target.pos - origin
            along = to_c.dot(direction)
            if along < -target.bound_radius or along > max_dist + target.bound_radius:
                continue
            if (to_c - direction * along).length() > target.bound_radius:
                continue
            for sphere_c, r in target.world_spheres():
                t = segment_sphere(origin, end, sphere_c, r)
                if t is not None:
                    hits.append((t * max_dist, target))
        if not hits:
            return None
        first = min(hits, key=lambda h: h[0])
        weak = [h for h in hits if h[1].kind == "weak_point" and h[0] - first[0] < 40]
        dist, target = min(weak, key=lambda h: h[0]) if weak else first
        return target, origin + direction * dist, dist

    def on_destroyed(self, entity, killer) -> None:
        entity.alive = False
        for listener in self.listeners:
            listener(entity, killer)
