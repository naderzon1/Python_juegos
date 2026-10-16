"""Jefes finales: naves capitales con fases, puntos débiles y patrones.

- Puntos débiles: generadores expuestos con vida propia. Mientras queden en
  pie, el núcleo recibe solo una fracción del daño (``core_armor``). Al
  destruir uno, el núcleo sufre una sacudida de daño y el generador deja de
  disparar; al caer todos, el núcleo queda totalmente vulnerable.
- Fases: cambian al bajar la vida del núcleo por debajo de cada umbral, con
  patrones nuevos y refuerzos.
- Patrones: ``spread`` (abanico), ``ring`` (anillo de proyectiles),
  ``missiles`` (salva guiada), ``beam`` (rayo con carga previa que avisa al
  jugador) y ``minions`` (refuerzos).
"""
from __future__ import annotations

import math
import random

from panda3d.core import Point3, Vec3

from game.combat.damage import Durability
from game.graphics import models
from game.ships.entity import Entity
from game.weapons.weapon import WeaponDef


class WeakPoint(Entity):
    def __init__(self, world, boss, node, hull: float, radius: float, index: int):
        super().__init__(world, node, "enemy", Durability(hull), f"Generador {index + 1}", "weak_point",
                         [(Point3(0, 0, 0), radius * 1.5)], radius * 1.6)
        self.boss = boss
        self.index = index
        self.shield_color = (1.0, 0.8, 0.3)
        self.hull_nodes = [node]
        self.fire_timer = random.uniform(1.5, 3.5)

    @property
    def pos(self) -> Point3:
        return self.node.getPos(self.world.render)


class Boss(Entity):
    def __init__(self, world, projectiles, audio, config, boss_id: str, galaxy: dict, rng: random.Random,
                 spawn_minions, announce):
        cfg = config.bosses[boss_id]
        diff = galaxy["difficulty"]
        model = models.build_boss(cfg["model"], cfg["radius"], int(cfg["weak_points"]), seed=len(boss_id))
        node = world.render.attachNewNode(boss_id)
        model.root.reparentTo(node)
        durability = Durability(cfg["hull"] * diff["hp_mult"], cfg["shield"] * diff["hp_mult"],
                                cfg.get("shield_regen", 0), 6.0, armor=float(cfg["core_armor"]))
        bound = max(p.length() + r for p, r in model.hit_spheres)
        super().__init__(world, node, "enemy", durability, cfg["name"], "boss", model.hit_spheres, bound)
        self.boss = True
        self.type_id = boss_id
        self.cfg = cfg
        self.model = model
        self.projectiles = projectiles
        self.audio = audio
        self.rng = rng
        self.spawn_minions = spawn_minions
        self.announce = announce
        self.hull_nodes = [model.hull]
        self.shield_color = tuple(cfg["model"]["glow"])
        self.phase_index = 0
        self.pattern_cursor = 0
        self.pattern_timer = 4.0
        self.beam = None  # [estado, tiempo, dirección]
        self.dying = 0.0
        self.weapons = {k: WeaponDef.from_config(k, config.weapons[k])
                        for k in ("boss_cannon", "enemy_missile", "boss_beam")}
        self.orbit_angle = rng.uniform(0, math.tau)
        self.weak_points: list[WeakPoint] = []
        glow, primary = cfg["model"]["glow"], cfg["model"]["primary"]
        for i, (p, r) in enumerate(model.weak_points):
            wp_node = models.build_weak_point(r, glow, primary)
            wp_node.reparentTo(model.root)
            wp_node.setPos(p)
            wp = WeakPoint(world, self, wp_node, cfg["weak_point_hull"] * diff["hp_mult"], r, i)
            self.weak_points.append(wp)
            world.add(wp)
        self.smoke_points: list[Point3] = []

    @property
    def phase(self) -> dict:
        return self.cfg["phases"][self.phase_index]

    @property
    def weak_alive(self) -> int:
        return sum(1 for w in self.weak_points if w.alive)

    def on_weak_point_destroyed(self, wp: WeakPoint) -> None:
        self.smoke_points.append(Point3(wp.node.getPos(self.model.root)))
        self.world.effects.big_explosion(wp.pos, max(2.0, wp.bound_radius / 6), tuple(self.cfg["model"]["glow"]))
        self.audio.play("explosion_big", 1.0, wp.pos)
        chunk = self.durability.max_hull * 0.06
        self.durability.hull = max(1.0, self.durability.hull - chunk)
        wp.node.hide()
        if self.weak_alive == 0:
            self.durability.armor = 1.0
            self.announce("¡Generadores destruidos! El núcleo es vulnerable")
        else:
            self.announce(f"Generador destruido ({self.weak_alive} restantes)")

    # --- comportamiento -----------------------------------------------------
    def update(self, dt: float, player) -> None:
        if self.dying > 0:
            self._update_death(dt)
            return
        if not self.alive:
            return
        self.durability.update(dt)
        self._check_phase()
        self._move(dt, player)
        self._attack(dt, player)
        for wp in self.weak_points:
            if wp.alive:
                wp.update_visuals(dt)
                wp.fire_timer -= dt
                if wp.fire_timer <= 0 and player.alive:
                    wp.fire_timer = self.rng.uniform(2.0, 3.6)
                    direction = player.pos + player.velocity * 0.6 - wp.pos
                    if direction.length() < 1600:
                        self.projectiles.fire("bolt", self, wp.pos, direction, self.weapons["boss_cannon"], "enemy")
        for p in self.smoke_points:
            if self.rng.random() < dt * 8:
                self.world.effects.smoke_puff(self.world.render.getRelativePoint(self.model.root, p), 6)
        self.update_visuals(dt)

    def _check_phase(self) -> None:
        ratio = self.durability.hull_ratio
        target = 0
        for i, phase in enumerate(self.cfg["phases"]):
            if ratio <= float(phase["threshold"]):
                target = i
        if target > self.phase_index:
            self.phase_index = target
            self.pattern_cursor = 0
            self.pattern_timer = 2.5
            self.announce(f"{self.cfg['name']}: FASE {target + 1}")
            self.world.effects.shockwave(self.pos, self.bound_radius * 2, tuple(self.cfg["model"]["glow"]))
            self.audio.play("boss_alert", 0.9)
            self.durability.shield = max(self.durability.shield, self.durability.max_shield * 0.3)
            if self.phase.get("minions"):
                self.spawn_minions(self.phase["minions"])

    def _move(self, dt: float, player) -> None:
        if not player.alive:
            return
        self.orbit_angle += dt * 0.05
        distance = self.bound_radius * 2.2 + 380
        goal = player.pos + Vec3(math.cos(self.orbit_angle), math.sin(self.orbit_angle), 0.15) * distance
        to_goal = goal - self.pos
        if to_goal.length() > 1:
            step = min(to_goal.length(), float(self.cfg["speed"]) * dt)
            to_goal.normalize()
            self.velocity = to_goal * float(self.cfg["speed"])
            self.node.setPos(self.pos + to_goal * step)
        # gira despacio para encararse con el jugador
        heading = self.node.getHpr()
        self.node.lookAt(player.pos)
        wanted = self.node.getHpr()
        self.node.setHpr(heading)
        dh = ((wanted.x - heading.x + 180) % 360) - 180
        dp = ((wanted.y - heading.y + 180) % 360) - 180
        self.node.setHpr(heading.x + max(-14 * dt, min(14 * dt, dh)), heading.y + max(-10 * dt, min(10 * dt, dp)), 0)

    def _attack(self, dt: float, player) -> None:
        if self.beam is not None:
            self._update_beam(dt, player)
            return
        self.pattern_timer -= dt
        if self.pattern_timer > 0 or not player.alive:
            return
        patterns = self.phase["patterns"]
        pattern = patterns[self.pattern_cursor % len(patterns)]
        self.pattern_cursor += 1
        self.pattern_timer = float(self.phase["interval"])
        getattr(self, "_p_" + pattern)(player)

    def _nose(self) -> Point3:
        return self.world.render.getRelativePoint(self.model.root, self.model.muzzles[-1])

    def _p_spread(self, player) -> None:
        origin = self._nose()
        aim = player.pos + player.velocity * ((player.pos - origin).length() / 430) * 0.7 - origin
        aim.normalize()
        side = aim.cross(Vec3(0, 0, 1))
        side.normalize()
        for i in range(-5, 6):
            d = aim + side * (i * 0.07)
            self.projectiles.fire("bolt", self, origin, d, self.weapons["boss_cannon"], "enemy")
        self.audio.play("shot_heavy", 1.0, origin)

    def _p_ring(self, player) -> None:
        origin = self.pos
        axis = player.pos - origin
        axis.normalize()
        u = axis.cross(Vec3(0, 0, 1))
        if u.length() < 1e-3:
            u = Vec3(1, 0, 0)
        u.normalize()
        w = axis.cross(u)
        count = 28
        for k in range(count):
            a = math.tau * k / count
            d = axis * 0.55 + (u * math.cos(a) + w * math.sin(a))
            self.projectiles.fire("bolt", self, origin + d * self.bound_radius * 0.4, d,
                                  self.weapons["boss_cannon"], "enemy", speed_mult=0.8)
        self.audio.play("pulse", 0.7, origin)

    def _p_missiles(self, player) -> None:
        sources = [w.pos for w in self.weak_points if w.alive] or [self._nose()]
        for i in range(4):
            origin = sources[i % len(sources)]
            self.projectiles.fire("missile", self, origin, player.pos - origin, self.weapons["enemy_missile"],
                                  "enemy", target=player)
        self.audio.play("missile_launch", 1.0, sources[0])

    def _p_minions(self, player) -> None:
        self.spawn_minions(self.phase.get("minions") or {"fighter": 2})

    def _p_beam(self, player) -> None:
        origin = self._nose()
        direction = player.pos - origin
        direction.normalize()
        self.beam = ["charge", 1.5, direction]
        self.announce("¡RAYO CARGANDO! Esquiva (Espacio)")
        self.audio.play("beam_charge", 1.0, origin)

    def _update_beam(self, dt: float, player) -> None:
        state, timer, direction = self.beam
        origin = self._nose()
        timer -= dt
        if state == "charge":
            self.projectiles.fire_beam(self, origin, direction, self.weapons["boss_beam"], "enemy", width=0.6,
                                       life=0.05, amount=0)
            if timer <= 0:
                self.beam = ["fire", 1.6, direction]
                self.audio.play("shot_laser", 1.0, origin, rate=0.5)
                return
        else:
            to_player = player.pos - origin
            to_player.normalize()
            direction = direction + (to_player - direction) * min(1.0, dt * 0.35)
            direction.normalize()
            self.projectiles.fire_beam(self, origin, direction, self.weapons["boss_beam"], "enemy", width=7.0,
                                       life=0.06, amount=self.weapons["boss_beam"].damage * dt * 1.6)
            if timer <= 0:
                self.beam = None
                return
        self.beam[1] = timer
        self.beam[2] = direction

    # --- destrucción --------------------------------------------------------
    def start_death(self) -> None:
        self.dying = 3.6
        self.targetable = False
        self.beam = None
        for wp in self.weak_points:
            wp.alive = False

    def _update_death(self, dt: float) -> None:
        self.dying -= dt
        glow = tuple(self.cfg["model"]["glow"])
        if self.rng.random() < dt * 9:
            r = self.bound_radius * 0.6
            offset = Vec3(self.rng.uniform(-r, r), self.rng.uniform(-r, r), self.rng.uniform(-r, r))
            self.world.effects.explosion(self.pos + offset, self.rng.uniform(2, 4), glow)
            self.audio.play("explosion_small", 1.0, self.pos)
        self.node.setH(self.node.getH() + dt * 6)
        if self.dying <= 0:
            self.world.effects.big_explosion(self.pos, self.bound_radius / 5, (1.0, 0.8, 0.5))
            self.audio.play("explosion_big", 1.0)
            self.destroy()

    @property
    def death_finished(self) -> bool:
        return self.dying <= 0 and not self.alive and self.node.isEmpty()
