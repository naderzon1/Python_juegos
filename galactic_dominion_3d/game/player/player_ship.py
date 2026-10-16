"""Nave del jugador: vuelo, energía, armas, fijación de objetivo y drones.

Modelo de vuelo arcade con inercia: el acelerador (W/S) fija una velocidad
de crucero y la nave se acerca a ella según su ``accel``; el impulso
multiplica la velocidad gastando energía; la maniobra evasiva da un salto
lateral con una barrena y unos instantes de invulnerabilidad que además
rompen el guiado de los misiles enemigos.
"""
from __future__ import annotations

import math
import random

from panda3d.core import Point3, Vec3

from game.ai.fsm import lead_point
from game.combat.damage import Durability
from game.graphics import models
from game.progression.evolution import evolution
from game.ships.entity import Ship
from game.weapons.weapon import WeaponDef, WeaponState


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class Drone:
    def __init__(self, player, wdef: WeaponDef, phase: float, life: float, damage_mult: float):
        cfg = {"hull": "dart", "scale": 0.45, "primary": [0.7, 0.75, 0.8], "secondary": [0.3, 0.9, 0.5],
               "glow": list(wdef.color)}
        self.model = models.build_enemy_ship(cfg, seed=int(phase * 10))
        self.node = player.world.render.attachNewNode("drone")
        self.model.root.reparentTo(self.node)
        self.phase = phase
        self.life = life
        self.weapon = WeaponState(wdef)
        self.damage_mult = damage_mult
        self.node.setPos(player.pos)

    def update(self, dt, player, projectiles) -> bool:
        self.life -= dt
        if self.life <= 0 or not player.alive:
            self.node.removeNode()
            return False
        self.phase += dt * 1.2
        offset = Vec3(math.cos(self.phase) * 14, -6 + math.sin(self.phase * 2) * 3, math.sin(self.phase) * 7)
        goal = player.world.render.getRelativePoint(player.node, Point3(offset))
        pos = self.node.getPos()
        self.node.setPos(pos + (goal - pos) * min(1.0, dt * 6))
        self.weapon.update(dt)
        target, best = None, self.weapon.d.range
        for enemy in player.world.hostiles_of("player"):
            d = (enemy.pos - self.node.getPos()).length()
            if d < best:
                target, best = enemy, d
        if target is not None:
            aim = lead_point(self.node.getPos(), target.pos, target.velocity, self.weapon.d.projectile_speed)
            self.node.lookAt(aim)
            if self.weapon.ready:
                direction = aim - self.node.getPos()
                projectiles.fire("bolt", player, self.node.getPos(), direction, self.weapon.d, "player",
                                 mult=self.damage_mult * player.stats.damage_mult)
                self.weapon.fire()
        else:
            self.node.setHpr(player.node.getHpr())
        return True

    def destroy(self) -> None:
        if not self.node.isEmpty():
            self.node.removeNode()


class PlayerShip(Ship):
    def __init__(self, world, projectiles, audio, config, profile, stats):
        ship_cfg = config.ships[profile.ship]
        self.evo = evolution(profile.level, config)
        model = models.build_player_ship(ship_cfg["model"], tier=self.evo.tier)
        durability = Durability(stats.max_hull, stats.max_shield, stats.shield_regen, stats.shield_delay)
        super().__init__(world, model, "player", durability, f"Tú ({self.evo.name})", "player", stats.max_speed,
                         stats.turn_rate)
        self.projectiles = projectiles
        self.audio = audio
        self.config = config
        self.stats = stats
        self.energy = stats.max_energy
        self.shield_color = tuple(ship_cfg["model"]["glow"])
        self.weapons: dict[str, WeaponState] = {}
        for wid in profile.unlocked_weapons:
            wd = WeaponDef.from_config(wid, config.weapons[wid])
            ammo = stats.missile_capacity if wd.uses_ammo else None
            self.weapons[wid] = WeaponState(wd, ammo)
        self.primaries = [w for w in profile.unlocked_weapons if config.weapons[w]["slot"] == "primary"]
        primary = profile.loadout.get("primary")
        self.primary_index = self.primaries.index(primary) if primary in self.primaries else 0
        self.secondary_id = profile.loadout.get("secondary")
        self.special_id = profile.loadout.get("special")
        self.throttle = 0.45
        self.yaw_rate = self.pitch_rate = self.roll_rate = 0.0
        self.bank = 0.0
        self.evade_timer = 0.0
        self.evade_cd = 0.0
        self.evade_dir = 1
        self.boosting = False
        self.lock_target = None
        self.lock_progress = 0.0
        self.lock_beep = 0.0
        self.drones: list[Drone] = []
        self.muzzle_index = 0
        self.events: list[str] = []

    # --- propiedades útiles para el HUD -------------------------------------
    @property
    def primary(self) -> WeaponState:
        return self.weapons[self.primaries[self.primary_index]]

    @property
    def secondary(self) -> WeaponState | None:
        return self.weapons.get(self.secondary_id) if self.secondary_id else None

    @property
    def special(self) -> WeaponState | None:
        return self.weapons.get(self.special_id) if self.special_id else None

    @property
    def evading(self) -> bool:
        return self.evade_timer > 0

    @property
    def locked(self) -> bool:
        return self.lock_target is not None and self.lock_progress >= 1.0

    @property
    def speed(self) -> float:
        return self.velocity.length()

    def axes(self):
        r = self.world.render
        fwd = r.getRelativeVector(self.node, Vec3(0, 1, 0))
        right = r.getRelativeVector(self.node, Vec3(1, 0, 0))
        up = r.getRelativeVector(self.node, Vec3(0, 0, 1))
        return fwd, right, up

    # --- actualización ------------------------------------------------------
    def update(self, dt: float, inp, target) -> None:
        if not self.alive:
            return
        self.events.clear()
        st = self.stats
        # rotación (ratón/mando → velocidad angular limitada por la maniobrabilidad)
        if dt > 0:
            want_yaw = _clamp(inp.yaw / dt, -st.turn_rate, st.turn_rate)
            want_pitch = _clamp(inp.pitch / dt, -st.turn_rate, st.turn_rate)
        else:
            want_yaw = want_pitch = 0.0
        k = min(1.0, 14 * dt)
        self.yaw_rate += (want_yaw - self.yaw_rate) * k
        self.pitch_rate += (want_pitch - self.pitch_rate) * k
        self.roll_rate += (-inp.roll * st.roll_rate - self.roll_rate) * min(1.0, 8 * dt)
        self.node.setHpr(self.node, self.yaw_rate * dt, self.pitch_rate * dt, self.roll_rate * dt)
        fwd, right, up = self.axes()

        # acelerador, impulso y desplazamiento lateral
        self.throttle = _clamp(self.throttle + inp.thrust * 0.9 * dt, -0.25, 1.0)
        self.boosting = inp.boost and self.energy > 4 and self.throttle > -0.05
        speed_target = st.max_speed * self.throttle
        if self.boosting:
            speed_target = st.max_speed * st.boost_mult
            self.energy -= st.boost_cost * dt
            if random.random() < 0.02:
                self.audio.play("boost", 0.3)
        desired = fwd * speed_target + right * inp.strafe * st.max_speed * 0.55

        # maniobra evasiva
        self.evade_cd = max(0.0, self.evade_cd - dt)
        if "evade" in inp.pressed and self.evade_cd <= 0 and self.energy >= 15:
            self.evade_dir = int(math.copysign(1, inp.strafe)) if inp.strafe else random.choice((-1, 1))
            self.velocity += right * self.evade_dir * 95
            self.evade_timer = 0.5
            self.evade_cd = 2.8
            self.energy -= 15
            self.durability.invulnerable = True
            self.audio.play("evade", 0.7)
            self.events.append("evade")
        accel = st.accel * (0.25 if self.evading else 1.0)
        self.velocity += (desired - self.velocity) * min(1.0, accel * dt)
        self.node.setPos(self.node.getPos() + self.velocity * dt)

        # inclinación visual del modelo (no afecta al vuelo)
        target_bank = -self.yaw_rate * 0.22 - inp.strafe * 14
        self.bank += (target_bank - self.bank) * min(1.0, 6 * dt)
        if self.evading:
            self.evade_timer -= dt
            spin = (1 - max(0.0, self.evade_timer) / 0.5) * 360 * self.evade_dir
            self.model.root.setR(self.bank + spin)
            if self.evade_timer <= 0:
                self.durability.invulnerable = False
        else:
            self.model.root.setR(self.bank)
        self.model.root.setP(-self.pitch_rate * 0.05)

        # energía y armas
        regen = st.energy_regen * (0.3 if self.boosting else 1.0)
        self.energy = _clamp(self.energy + regen * dt, 0.0, st.max_energy)
        for weapon in self.weapons.values():
            weapon.update(dt)
        if "weapon_next" in inp.pressed and len(self.primaries) > 1:
            self.primary_index = (self.primary_index + 1) % len(self.primaries)
            self.audio.play("ui_click", 0.5)
            self.events.append("weapon")
        if inp.fire_primary and self.primary.can_fire(self.energy):
            self._fire_primary(self.primary, target)
        sec = self.secondary
        if inp.fire_secondary and sec is not None and sec.can_fire(self.energy):
            self._fire_secondary(sec, target)
        spec = self.special
        if "fire_special" in inp.pressed and spec is not None:
            if spec.can_fire(self.energy):
                self._fire_special(spec, target)
            else:
                self.audio.play("ui_error", 0.4)
        self._update_lock(dt, target)
        self.drones = [d for d in self.drones if d.update(dt, self, self.projectiles)]
        self.durability.update(dt)
        self.update_engines(1.0 if self.boosting else 0.0)
        self.update_visuals(dt)

    # --- disparos -------------------------------------------------------------
    def _muzzle(self) -> Point3:
        muzzles = self.model.muzzles or [Point3(0, 5, 0)]
        self.muzzle_index = (self.muzzle_index + 1) % len(muzzles)
        return self.world.render.getRelativePoint(self.model.root, muzzles[self.muzzle_index])

    def _fire_primary(self, weapon: WeaponState, target) -> None:
        wd = weapon.d
        fwd, right, up = self.axes()
        st = self.stats
        evo = self.evo
        if wd.kind == "beam":
            origin = self.pos + fwd * 6
            self.projectiles.fire_beam(self, origin, fwd, wd, "player", st.damage_mult, st.crit_bonus,
                                       width=0.5 * evo.bolt_size)
        else:
            convergence = self.pos + fwd * 420
            assist = self._aim_assist(target, wd.projectile_speed)
            spread = math.tan(math.radians(wd.spread_deg))
            # la evolución Mk III/V convierte los disparos únicos en ráfagas dobles/triples
            count, mult = wd.projectiles, st.damage_mult
            if wd.projectiles == 1 and evo.extra_projectiles:
                count += evo.extra_projectiles
                mult *= evo.shot_damage
            for _ in range(count):
                origin = self._muzzle()
                direction = (assist if assist is not None else convergence) - origin
                direction.normalize()
                direction += right * random.uniform(-spread, spread) + up * random.uniform(-spread, spread)
                self.projectiles.fire("bolt", self, origin, direction, wd, "player", mult, st.crit_bonus,
                                      inherit=self.velocity, size_mult=evo.bolt_size)
        self.energy -= wd.energy_cost
        weapon.fire()
        self._weapon_sound(wd.sound, 0.55)

    def _aim_assist(self, target, speed: float):
        """Asistencia de puntería: si el objetivo está casi en la mira (≤ 4,5°), apunta a su anticipación."""
        if target is None or not target.alive or speed <= 0:
            return None
        to_target = target.pos - self.pos
        dist = to_target.length()
        if dist < 1 or dist > 1500:
            return None
        fwd, _, _ = self.axes()
        if fwd.dot(to_target / dist) < math.cos(math.radians(4.5)):
            return None
        return lead_point(self.pos, target.pos, target.velocity - self.velocity, speed)

    def _fire_secondary(self, weapon: WeaponState, target) -> None:
        wd = weapon.d
        fwd, right, up = self.axes()
        st = self.stats
        if wd.kind == "missile":
            homing = self.lock_target if self.locked else None
            origin = self.pos - up * 1.2 + right * random.choice((-1.5, 1.5))
            self.projectiles.fire("missile", self, origin, fwd, wd, "player", st.damage_mult, st.crit_bonus,
                                  target=homing, size_mult=self.evo.bolt_size)
            self.events.append("missile")
        elif wd.kind == "drones":
            for drone in self.drones:
                drone.destroy()
            count = max(1, int(st.drone_count))
            self.drones = [Drone(self, wd, i * 2 * math.pi / count, wd.duration, st.drone_damage_mult)
                           for i in range(count)]
            self.events.append("drones")
        self.energy -= wd.energy_cost
        weapon.fire()
        self._weapon_sound(wd.sound, 0.6)

    def _fire_special(self, weapon: WeaponState, target) -> None:
        wd = weapon.d
        st = self.stats
        fwd, _, _ = self.axes()
        if wd.kind == "pulse":
            self.world.area_damage(self.pos, wd.explosion_radius, wd, self, st.damage_mult, st.crit_bonus, "player")
            self.world.effects.shockwave(self.pos, wd.explosion_radius, wd.color)
            self.world.effects.shake = max(self.world.effects.shake, 0.5)
        elif wd.kind == "torpedo":
            homing = self.lock_target if self.locked else target
            self.projectiles.fire("torpedo", self, self.pos + fwd * 6, fwd, wd, "player", st.damage_mult,
                                  st.crit_bonus, target=homing, size_mult=self.evo.bolt_size)
        self.energy -= wd.energy_cost
        weapon.fire()
        self._weapon_sound(wd.sound, 0.8)
        self.events.append("special")

    def _weapon_sound(self, name: str, volume: float) -> None:
        """Las etapas superiores suenan más graves y potentes, con una capa de impacto desde Mk III."""
        evo = self.evo
        self.audio.play(name, min(1.0, volume * evo.sound_volume), rate=evo.sound_rate)
        if evo.tier >= 3:
            self.audio.play("shot_layer", min(1.0, 0.25 + 0.08 * evo.tier), rate=evo.sound_rate)

    def _update_lock(self, dt: float, target) -> None:
        if target is not self.lock_target:
            self.lock_target = target
            self.lock_progress = 0.0
        if target is None or not target.alive:
            self.lock_target = None
            self.lock_progress = 0.0
            return
        to_target = target.pos - self.pos
        dist = to_target.length()
        fwd, _, _ = self.axes()
        cos = fwd.dot(to_target / max(dist, 1e-3))
        if dist < self.stats.lock_range and cos > math.cos(math.radians(16)):
            before = self.lock_progress
            self.lock_progress = min(1.0, self.lock_progress + dt / self.stats.lock_time)
            if self.lock_progress < 1.0:
                self.lock_beep -= dt
                if self.lock_beep <= 0:
                    self.lock_beep = 0.18
                    self.audio.play("lock_beep", 0.35)
            elif before < 1.0:
                self.audio.play("lock_done", 0.5)
        else:
            self.lock_progress = max(0.0, self.lock_progress - dt * 1.5)

    def destroy(self) -> None:
        for drone in self.drones:
            drone.destroy()
        self.drones.clear()
        super().destroy()
