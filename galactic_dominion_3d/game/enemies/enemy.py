"""Naves enemigas controladas por la máquina de estados de ``game.ai.fsm``.

Las estaciones militares son torretas fijas: no se mueven, pero giran sus
cañones y disparan desde varios puntos. Las naves de élite tienen más vida,
daño y velocidad, un brillo dorado y mejores recompensas.
"""
from __future__ import annotations

import random

from panda3d.core import Point3, Vec3

from game.ai.fsm import Brain, Perception
from game.combat.damage import Durability
from game.graphics import models
from game.ships.entity import Ship
from game.weapons.weapon import WeaponDef, WeaponState


class EnemyShip(Ship):
    def __init__(self, world, projectiles, audio, config, type_id: str, elite: bool, galaxy: dict,
                 rng: random.Random, side: int = 1):
        cfg = config.enemies[type_id]
        diff = galaxy["difficulty"]
        e = config.elite if elite else {"hull_mult": 1, "shield_mult": 1, "damage_mult": 1, "speed_mult": 1}
        model_cfg = dict(cfg["model"])
        if elite:
            model_cfg["glow"] = config.elite["glow"]
        model = models.build_enemy_ship(model_cfg, seed=rng.randrange(1000))
        hull = cfg["hull"] * diff["hp_mult"] * e["hull_mult"]
        shield = cfg["shield"] * diff["hp_mult"] * e["shield_mult"]
        durability = Durability(hull, shield, cfg.get("shield_regen", 0) * diff["hp_mult"], 3.5)
        speed = cfg["speed"] * e["speed_mult"]
        super().__init__(world, model, "enemy", durability, cfg["name"] + (" (élite)" if elite else ""),
                         "station" if cfg.get("static") else "fighter", speed, cfg["turn_rate"])
        self.type_id = type_id
        self.cfg = cfg
        self.elite = elite
        self.alien = type_id.startswith("alien")
        self.projectiles = projectiles
        self.audio = audio
        self.damage_mult = e["damage_mult"]
        self.static = bool(cfg.get("static"))
        self.brain = Brain(cfg["ai"], rng, static=self.static, side=side)
        self.weapons = [WeaponState(WeaponDef.from_config(w, config.weapons[w])) for w in cfg["weapons"]]
        self.gun = next((w for w in self.weapons if w.d.kind != "missile"), self.weapons[0])
        self.missile = next((w for w in self.weapons if w.d.kind == "missile"), None)
        self.shield_color = (1.0, 0.45, 0.3) if not self.alien else (0.5, 1.0, 0.4)
        if elite:
            self.shield_color = (1.0, 0.85, 0.3)
        self.rng = rng
        self.target = None
        self.defend_point: Point3 | None = None
        self.may_attack = True
        self.muzzle_index = 0
        self.throttle = 0.8

    def update(self, dt: float) -> None:
        if not self.alive:
            return
        for w in self.weapons:
            w.update(dt)
        self.durability.update(dt)
        target = self.target if (self.target is not None and self.target.alive) else None
        fwd = self.forward()
        perception = Perception(
            pos=self.pos, forward=fwd, hull_ratio=self.durability.hull_ratio,
            target_pos=target.pos if target else None,
            target_vel=target.velocity if target else Vec3(0, 0, 0),
            target_forward=target.forward() if target else Vec3(0, 1, 0),
            projectile_speed=self.gun.d.projectile_speed, weapon_range=self.gun.d.range,
            under_fire=(self.world.time - self.last_hit_time) < 1.5, may_attack=self.may_attack,
            defend_point=self.defend_point, dt=dt)
        cmd = self.brain.update(perception)
        if self.static:
            self.node.setH(self.node.getH() + 3 * dt)  # la estación gira despacio sobre su eje
        else:
            self.turn_towards(cmd.direction, dt)
            self.throttle = cmd.throttle
            desired = self.forward() * self.max_speed * cmd.throttle
            self.velocity += (desired - self.velocity) * min(1.0, 2.2 * dt)
            self._separate(dt)
            self.node.setPos(self.node.getPos() + self.velocity * dt)
        if target is not None:
            if cmd.fire and self.gun.ready:
                self._fire_gun(cmd.aim_point or target.pos)
            if cmd.fire_missile and self.missile is not None and self.missile.ready:
                self._fire_missile(target)
        self.update_engines()
        self.update_visuals(dt)

    def _separate(self, dt: float) -> None:
        """Evita que los enemigos se amontonen o choquen entre sí."""
        push = Vec3(0, 0, 0)
        my_pos = self.pos
        for other in self.world.entities:
            if other is self or not other.alive or other.faction != "enemy":
                continue
            offset = my_pos - other.pos
            d = offset.length()
            limit = (self.bound_radius + other.bound_radius) * 2.2
            if 1e-3 < d < limit:
                push += offset / d * (1 - d / limit)
        if push.length() > 0:
            self.velocity += push * 60 * dt

    def _muzzle(self) -> Point3:
        muzzles = self.model.muzzles or [Point3(0, self.model.length * 0.5, 0)]
        self.muzzle_index = (self.muzzle_index + 1) % len(muzzles)
        return self.world.render.getRelativePoint(self.model.root, muzzles[self.muzzle_index])

    def _fire_gun(self, aim: Point3) -> None:
        wd = self.gun.d
        origin = self._muzzle()
        direction = aim - origin
        if self.static and direction.length() > wd.range:
            return
        direction.normalize()
        spread = wd.spread_deg / 57.3 * (1.6 - float(self.cfg["ai"].get("accuracy", 0.6)))
        direction += Vec3(self.rng.uniform(-spread, spread), self.rng.uniform(-spread, spread),
                          self.rng.uniform(-spread, spread))
        if wd.kind == "beam":
            self.projectiles.fire_beam(self, origin, direction, wd, "enemy", self.damage_mult)
        else:
            self.projectiles.fire("bolt", self, origin, direction, wd, "enemy", self.damage_mult,
                                  inherit=self.velocity if not self.static else None)
        self.gun.fire()
        self.audio.play(wd.sound, 0.4, origin)

    def _fire_missile(self, target) -> None:
        wd = self.missile.d
        origin = self._muzzle()
        self.projectiles.fire("missile", self, origin, target.pos - origin, wd, "enemy", self.damage_mult,
                              target=target)
        self.missile.fire()
        self.audio.play(wd.sound, 0.5, origin)
