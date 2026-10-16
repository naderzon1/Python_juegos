"""Sesión de vuelo: une todos los sistemas durante una misión.

Ciclo de vida: ``build_steps`` (carga repartida en fotogramas) → combate →
desenlace (éxito: el portal se activa y se salta; fracaso: explosión y
cámara cinemática) → ``app.on_mission_end(resultado)``.
"""
from __future__ import annotations

import math
import random

from panda3d.core import Point3, Vec3

from game.ai.fsm import SquadCoordinator
from game.combat.damage import DamageInfo
from game.combat.projectiles import ProjectileSystem
from game.combat.world import CombatWorld
from game.core.camera_rig import ChaseCamera
from game.enemies.boss import Boss
from game.enemies.enemy import EnemyShip
from game.galaxies.scene import GalaxyScene
from game.graphics.effects import Effects
from game.missions.mission import (FAILED, SUCCESS, MissionRuntime, WaveDirector, empty_rewards, kill_rewards,
                                   merge_rewards)
from game.missions.tutorial import Tutorial
from game.player.controller import InputState
from game.player.player_ship import PlayerShip
from game.ships.allies import AllyStation, Freighter, SalvagePod
from game.ships.stats import compute_ship_stats
from game.ui.hud import HUD
from game.ui.theme import CYAN, GOLD, GREEN, MAGENTA, RED


class FlightSession:
    def __init__(self, app, galaxy_id: str, mission_id: str):
        self.app = app
        self.config = app.game_config
        galaxy, mission = self.config.mission(mission_id)
        assert galaxy["id"] == galaxy_id
        self.galaxy, self.mission_cfg = galaxy, mission
        self.quality = app.settings.quality()
        self.rng = random.Random()
        self.scene = GalaxyScene(app, galaxy, self.quality, mission)
        self.state = "loading"
        self.paused = False
        self.player = None
        self.target = None
        self.boss = None
        self.enemies: list = []
        self.allies: list = []
        self.pods: list = []
        self.queue: list = []
        self.earned = empty_rewards()
        self.kills = 0
        self.time = 0.0
        self.outro = 0.0
        self.time_scale = 1.0
        self.slowmo = 0.0
        self.hazard_alert = None
        self.out_of_bounds = False
        self.last_input = InputState()
        self.music_timer = 0.0
        self.alarm_timer = 0.0
        self.boss_timer = None
        self.tutorial = None
        self.result = None

    # --- carga ----------------------------------------------------------------
    def build_steps(self):
        yield from self.scene.build_steps()
        yield "Preparando el combate"
        self._setup()

    def _setup(self) -> None:
        app = self.app
        cfg = self.config
        self.effects = Effects(app.render, int(self.quality["particle_cap"]), self.rng)
        self.world = CombatWorld(app, cfg, self.effects, app.audio, self.rng)
        self.world.difficulty = self.galaxy["difficulty"]
        self.world.listeners.append(self.on_destroyed)
        self.world.hit_listeners.append(self.on_hit)
        self.projectiles = ProjectileSystem(self.world, self.effects, app.audio)
        self.projectiles.rocks = self.scene.hazard_rocks
        stats = compute_ship_stats(app.profile, cfg)
        self.player = PlayerShip(self.world, self.projectiles, app.audio, cfg, app.profile, stats)
        self.player.node.setPos(0, -420, 0)
        self.world.add(self.player)
        self.camera = ChaseCamera(app, float(app.settings["fov"]))
        self.hud = HUD(app, self)
        self.mission = MissionRuntime(self.mission_cfg)
        self.director = WaveDirector(self.mission_cfg.get("waves", []), self.mission_cfg.get("reinforce_at", 0),
                                     bool(self.mission_cfg.get("loop_waves")))
        self.squad = SquadCoordinator(max_attackers=2 + int(self.galaxy["tier"]) // 2)
        self.max_enemies = int(self.quality.get("max_enemies", 14))
        mtype, params = self.mission_cfg["type"], self.mission_cfg.get("params", {})
        if mtype == "defend_station":
            station = AllyStation(self.world, Point3(0, 260, 0), float(params["station_hull"]),
                                  "Bastión de la Alianza" if self.galaxy["id"] == "void" else "Estación Orión-7")
            self.world.add(station)
            self.allies.append(station)
        elif mtype == "escort":
            freighter = Freighter(self.world, Point3(60, -300, -20), self.scene.portal_pos + Vec3(0, -40, -60),
                                  float(params["speed"]), float(params["ally_hull"]))
            self.world.add(freighter)
            self.allies.append(freighter)
            self.player.node.setPos(-40, -380, 0)
        elif mtype == "recover_materials":
            arena = self.scene.arena_radius
            for i in range(int(params["count"]) + 2):
                ang = self.rng.uniform(0, math.tau)
                dist = self.rng.uniform(arena * 0.25, arena * 0.75)
                self.pods.append(SalvagePod(app.render, Point3(math.cos(ang) * dist, math.sin(ang) * dist,
                                                                self.rng.uniform(-120, 120))))
        elif mtype == "boss":
            self.boss_timer = 6.0
        if self.mission_cfg.get("tutorial") and not app.profile.flags.get("tutorial_done"):
            self.tutorial = Tutorial(self.hud)
        app.controller.capture(True)
        app.audio.start_engine()
        app.audio.play_music(self.galaxy["music"])
        self.hud.banner(self.mission_cfg["name"], self.mission_cfg["description"], GOLD, 5.0)
        self.state = "combat"

    # --- bucle ----------------------------------------------------------------
    def update(self, dt: float) -> None:
        if self.state == "loading" or self.player is None:
            return
        inp = self.app.controller.poll()
        self.last_input = inp
        if "pause" in inp.pressed and self.state == "combat":
            self.app.toggle_pause()
            return
        if self.paused:
            return
        dt = min(dt, 0.05)
        if self.slowmo > 0:
            self.slowmo -= dt
            self.time_scale = 0.35
        else:
            self.time_scale = min(1.0, self.time_scale + dt)
        sdt = dt * self.time_scale
        self.time += sdt
        self.world.time += sdt
        self._update_targeting(inp)
        if self.player.alive:
            control = inp if self.state in ("combat", "success") else InputState()
            self.player.update(sdt, control, self.target)
        self._update_enemies(sdt)
        self._update_allies(sdt)
        self._update_environment(sdt)
        self.projectiles.update(sdt)
        self.effects.update(sdt)
        self.world.cleanup()
        self.enemies = [e for e in self.enemies if e.alive]
        if self.tutorial is not None:
            self.tutorial.update(dt, self)
        self._update_spawning(sdt)
        self.mission.update(sdt)
        if self.mission_cfg["type"] == "destroy_fleet" and self.director.all_spawned and not self.queue \
                and not self.enemies:
            self.mission.on_fleet_cleared()
        self._update_camera(dt)
        self._update_music(dt)
        self._update_alarm(dt)
        self.app.overlays.update(dt, self.player.alive and self.player.durability.hull_ratio < 0.25)
        self.hud.update(dt)
        self._update_outcome(dt)

    def _update_targeting(self, inp: InputState) -> None:
        p = self.player
        candidates = [e for e in self.world.hostiles_of("player") if e.targetable]
        if self.target is not None and (not self.target.alive or not self.target.targetable):
            self.target = None
        if not candidates:
            return
        by_dist = sorted(candidates, key=lambda e: (e.pos - p.pos).length())
        if "target_nearest" in inp.pressed:
            self.target = by_dist[0]
            self.app.audio.play("ui_click", 0.4)
        elif "target_next" in inp.pressed:
            if self.target in by_dist:
                self.target = by_dist[(by_dist.index(self.target) + 1) % len(by_dist)]
            else:
                self.target = self._best_in_front(candidates) or by_dist[0]
            self.app.audio.play("ui_click", 0.4)
        elif self.target is None:
            self.target = self._best_in_front(candidates)

    def _best_in_front(self, candidates):
        p = self.player
        fwd = p.forward()
        best, score = None, -1.0
        for e in candidates:
            to = e.pos - p.pos
            dist = to.length()
            if dist > 2500:
                continue
            cos = fwd.dot(to / max(dist, 1))
            if cos > 0.85 and cos > score:
                best, score = e, cos
        return best

    def _update_enemies(self, dt: float) -> None:
        fighters = [e for e in self.enemies if not e.static]
        self.squad.update(dt, fighters)
        objective_allies = [a for a in self.allies if a.alive]
        for i, enemy in enumerate(self.enemies):
            if objective_allies and not enemy.static and i % 2 == 0:
                enemy.target = objective_allies[0]
            else:
                enemy.target = self.player if self.player.alive else None
            enemy.may_attack = enemy.static or self.squad.may_attack(enemy)
            enemy.update(dt)
        if self.boss_timer is not None:
            self.boss_timer -= dt
            if self.boss_timer <= 0:
                self.boss_timer = None
                self._spawn_boss()
        if self.boss is not None:
            self.boss.update(dt, self.player)

    def _update_allies(self, dt: float) -> None:
        for ally in self.allies:
            if ally.alive:
                ally.update(dt)
                if isinstance(ally, Freighter):
                    self.mission.on_escort_progress(ally.travelled)
        for pod in self.pods:
            if pod.update(dt, self.player.pos):
                self.mission.on_pickup()
                self.app.audio.play("pickup", 0.6)
                mat = self.galaxy["material"]
                merge_rewards(self.earned, {"materials": {mat: 2}})
                self.hud.message(f"Contenedor recuperado (+2 {self.config.material_name(mat)})", GREEN)
        self.pods = [p for p in self.pods if not p.collected]

    def _update_environment(self, dt: float) -> None:
        self.hazard_alert = None
        ships = [self.player] + self.enemies if self.player.alive else list(self.enemies)
        for hazard in self.scene.hazards:
            for ship in ships:
                text = hazard.affect(ship, dt)
                if text and ship is self.player:
                    self.hazard_alert = text
        for ship in ships:
            radius = ship.bound_radius * 0.6
            pos = ship.pos
            for center, r in self.scene.hazard_rocks:
                offset = pos - center
                dist = offset.length()
                if dist < r + radius and dist > 1e-3:
                    normal = offset / dist
                    ship.node.setPos(center + normal * (r + radius + 0.5))
                    impact = -ship.velocity.dot(normal)
                    if impact > 0:
                        ship.velocity += normal * impact * 1.6
                        if impact > 8:
                            ship.apply_damage(DamageInfo(impact * 0.5), center + normal * r)
                            self.effects.sparks(center + normal * r, (1, 0.8, 0.5), 10, normal)
                            self.app.audio.play("impact", 0.8, pos)
                            if ship is self.player:
                                self.camera.add_trauma(min(0.6, impact / 60))
        arena = self.scene.arena_radius
        dist = self.player.pos.length()
        self.out_of_bounds = dist > arena
        if dist > arena * 1.12 and self.player.alive:
            pull = -self.player.pos
            pull.normalize()
            self.player.velocity += pull * (dist - arena * 1.12) * 0.6 * dt
        for enemy in self.enemies:
            if not enemy.static and enemy.pos.length() > arena * 1.5:
                enemy.velocity += -enemy.pos / max(1.0, enemy.pos.length()) * 40 * dt

    def _update_spawning(self, dt: float) -> None:
        if self.state != "combat":
            return
        if self.tutorial is not None and not self.tutorial.enemies_allowed:
            return
        alive = len(self.enemies) + len(self.queue)
        for group in self.director.update(dt, alive):
            for _ in range(group["count"]):
                self.queue.append((group["type"], group["elite"], None))
        while self.queue and len(self.enemies) < self.max_enemies:
            type_id, elite, near = self.queue.pop(0)
            self._spawn(type_id, elite, near)

    def _spawn(self, type_id: str, elite: bool, near: Point3 | None = None) -> EnemyShip:
        side = 1 if len(self.enemies) % 2 == 0 else -1
        enemy = EnemyShip(self.world, self.projectiles, self.app.audio, self.config, type_id, elite, self.galaxy,
                          self.rng, side)
        arena = self.scene.arena_radius
        if enemy.static:
            ang = self.rng.uniform(0, math.tau)
            pos = Point3(math.cos(ang) * arena * 0.55, math.sin(ang) * arena * 0.55 + 300, self.rng.uniform(-80, 80))
            for other in self.enemies:
                if other.static and (other.pos - pos).length() < 500:
                    pos = Point3(-pos.x, -pos.y + 300, pos.z)
        else:
            anchor = near or (self.allies[0].pos if self.allies and self.rng.random() < 0.5 else self.player.pos)
            fwd = self.player.forward()
            for _ in range(8):
                ang = self.rng.uniform(0, math.tau)
                direction = Vec3(math.cos(ang), math.sin(ang), self.rng.uniform(-0.25, 0.25))
                if near is None and direction.dot(fwd) < -0.3:
                    continue  # que no aparezcan justo a la espalda
                break
            direction.normalize()
            pos = anchor + direction * (self.rng.uniform(180, 320) if near else self.rng.uniform(750, 1100))
            if pos.length() > arena * 1.25:
                pos = pos / pos.length() * arena * 1.2
            enemy.node.lookAt(self.player.pos)
            stations = [e for e in self.enemies if e.static]
            if stations and self.rng.random() < 0.5:
                enemy.defend_point = stations[self.rng.randrange(len(stations))].pos
            first_wave = self.director.waves_spawned <= 1 and self.mission_cfg["type"] in ("destroy_fleet",)
            if first_wave:
                enemy.brain.start_patrol(pos)
        enemy.node.setPos(pos)
        self.world.add(enemy)
        self.enemies.append(enemy)
        if elite:
            self.hud.message(f"¡{enemy.name} detectado!", GOLD, 5)
        return enemy

    def _spawn_boss(self) -> None:
        boss_id = self.mission_cfg["params"]["boss"]
        fwd = self.player.forward()
        self.boss = Boss(self.world, self.projectiles, self.app.audio, self.config, boss_id, self.galaxy, self.rng,
                         self.spawn_minions, self.announce)
        self.boss.node.setPos(self.player.pos + fwd * 1100 + Vec3(0, 0, 80))
        self.boss.node.lookAt(self.player.pos)
        self.world.add(self.boss)
        self.app.audio.play("boss_alert", 1.0)
        self.app.audio.play_music("boss")
        self.hud.banner("¡JEFE A LA VISTA!", self.boss.name, MAGENTA, 4.0)
        self.target = self.boss

    MAX_BOSS_ESCORT = 4  # refuerzos del jefe vivos a la vez: la pelea es contra el jefe, no contra una marea

    def spawn_minions(self, groups: dict) -> None:
        near = self.boss.pos if self.boss is not None else None
        spawned = 0
        for type_id, count in groups.items():
            for _ in range(int(count)):
                if len(self.enemies) + len(self.queue) < self.MAX_BOSS_ESCORT:
                    self.queue.append((type_id, False, near))
                    spawned += 1
        if spawned:
            self.hud.message("¡Refuerzos enemigos!", RED)

    def announce(self, text: str) -> None:
        self.hud.banner(text, "", MAGENTA, 3.0)

    def objective_points(self) -> list:
        points = [a.pos for a in self.allies if a.alive]
        points += [p.pos for p in self.pods[:6]]
        if self.state == "success":
            points.append(self.scene.portal_pos)
        return points

    def _update_camera(self, dt: float) -> None:
        if self.effects.shake > 0:
            self.camera.add_trauma(self.effects.shake * 0.5)
            self.effects.shake = 0.0
        if self.player.alive:
            ratio = self.player.speed / max(1.0, self.player.stats.max_speed)
            self.camera.update(dt, self.player, min(1.5, ratio), self.player.boosting)
        else:
            self.camera.orbit(dt, self.player.node.getPos(), 70, self.time)
        cam_pos = self.app.camera.getPos(self.app.render)
        self.world.camera_pos = cam_pos
        self.app.audio.listener = self.app.camera
        self.scene.update(dt, cam_pos, self.player.node.getPos())
        evo = self.player.evo
        self.app.audio.set_engine(max(0.0, self.player.throttle), self.player.boosting, evo.sound_rate,
                                  evo.sound_volume)

    def _update_alarm(self, dt: float) -> None:
        """Alarma sonora con el casco crítico o con misiles enemigos guiados hacia el jugador."""
        p = self.player
        danger = p.alive and self.state == "combat" and (
            p.durability.hull_ratio < 0.3 or bool(self.projectiles.incoming_missiles(p)))
        self.alarm_timer -= dt
        if danger and self.alarm_timer <= 0:
            self.app.audio.play("alarm", 0.35)
            self.alarm_timer = 2.5

    def _update_music(self, dt: float) -> None:
        if self.boss is not None and self.boss.alive:
            return
        near = any((e.pos - self.player.pos).length() < 1400 for e in self.enemies)
        self.music_timer = 6.0 if near else self.music_timer - dt
        self.app.audio.play_music("combat" if self.music_timer > 0 else self.galaxy["music"])

    def _update_outcome(self, dt: float) -> None:
        if self.state == "combat":
            if self.mission.state == SUCCESS:
                self.state = "success"
                self.outro = 5.0
                self.director.stop()
                self.player.durability.invulnerable = True
                self.scene.set_portal_strength(1.0)
                self.app.audio.play("victory", 0.8)
                self.hud.banner("MISIÓN CUMPLIDA", "El portal de salto está activo", GREEN, 4.5)
                self.hud.tutorial("")
            elif self.mission.state == FAILED:
                self.state = "failed"
                self.outro = 4.0
                self.director.stop()
                self.app.audio.play("defeat", 0.8)
                self.hud.banner("MISIÓN FALLIDA", self.mission.fail_reason, RED, 4.0)
            return
        if self.state in ("success", "failed"):
            self.outro -= dt
            if self.state == "success" and self.outro < 1.6:
                if self.outro + dt >= 1.6:
                    self.app.audio.play("jump", 0.9)
                self.app.overlays.set_jump(1.0 - max(0.0, self.outro - 0.2) / 1.4)
            if self.outro <= 0:
                self.state = "done"
                self.app.on_mission_end(self._result())

    def _result(self) -> dict:
        return {"success": self.mission.state == SUCCESS, "reason": self.mission.fail_reason,
                "galaxy": self.galaxy, "mission": self.mission_cfg, "earned": self.earned, "kills": self.kills,
                "time": self.time, "player_died": not self.player.alive}

    # --- sucesos del combate ------------------------------------------------
    def on_destroyed(self, entity, killer) -> None:
        if entity is self.player:
            self.effects.big_explosion(entity.pos, 2.5, (1.0, 0.6, 0.3))
            self.app.audio.play("explosion_big", 1.0)
            entity.node.hide()
            for drone in entity.drones:
                drone.destroy()
            self.mission.on_player_destroyed()
            self.slowmo = 1.2
            return
        if entity.kind == "weak_point":
            entity.boss.on_weak_point_destroyed(entity)
            merge_rewards(self.earned, {"xp": 40})
            return
        if entity.boss:
            entity.start_death()
            self.slowmo = 1.5
            self.mission.on_enemy_killed(entity.type_id, boss=True)
            self.hud.banner(f"¡{entity.name} DERROTADO!", "", GOLD, 4.0)
            return
        if entity.faction == "enemy":
            size = max(1.0, entity.bound_radius / 5)
            self.effects.explosion(entity.pos, size, entity.model.glow_color)
            self.app.audio.play("explosion_big" if size > 2.5 else "explosion_small", 1.0, entity.pos)
            rewards = kill_rewards(entity.cfg, self.galaxy, entity.elite, self.rng, self.config)
            merge_rewards(self.earned, rewards)
            self.kills += 1
            text = f"{entity.name} destruido  +{rewards['xp']} XP  +{rewards['credits']} CR"
            for mat, amount in rewards["materials"].items():
                text += f"  +{amount} {self.config.material_name(mat)}"
            self.hud.message(text, GOLD if entity.elite else CYAN)
            for item in rewards["items"]:
                rarity = self.config.economy["rarities"][item["rarity"]]
                self.hud.message(f"Objeto: {item['name']} [{rarity['name']}]", tuple(rarity["color"]) + (1,), 6)
            self.mission.on_enemy_killed(entity.type_id, elite=entity.elite)
            if entity is self.target:
                self.target = None
            entity.destroy()
            return
        if entity.kind == "ally":
            self.effects.big_explosion(entity.pos, 4.0, (1.0, 0.7, 0.4))
            self.app.audio.play("explosion_big", 1.0, entity.pos)
            self.mission.on_ally_destroyed(entity.name)
            entity.node.hide()

    def on_hit(self, target, source, result) -> None:
        if source is self.player and target.faction == "enemy" and (result.hull_damage or result.shield_damage):
            self.hud.hit(result.crit)
        if target is self.player:
            if result.hull_damage > 0:
                self.camera.add_trauma(0.35)
                self.app.overlays.pulse_damage(0.45)
            elif result.shield_damage > 0:
                self.camera.add_trauma(0.12)
        elif target in self.allies and self.rng.random() < 0.05:
            self.hud.message(f"¡{target.name} bajo ataque!", RED, 2.5)

    # --- limpieza -------------------------------------------------------------
    def destroy(self) -> None:
        if self.player is not None:
            self.hud.destroy()
            for entity in list(self.world.entities):
                entity.destroy()
            if self.boss is not None and not self.boss.node.isEmpty():
                self.boss.node.removeNode()
            for pod in self.pods:
                pod.destroy()
            self.projectiles.destroy()
            self.effects.destroy()
            self.camera.reset()
        self.app.controller.capture(False)
        self.app.audio.stop_engine()
        self.app.overlays.clear()
        self.scene.destroy()
