"""Misiones basadas en objetivos, oleadas enemigas y recompensas.

Este módulo no conoce el motor 3D: la sesión de vuelo le informa de los
sucesos (enemigo destruido, contenedor recogido, aliado destruido...) y él
decide el estado de la misión. Así se puede probar con pytest.
"""
from __future__ import annotations

import random

from game.core.config import GameConfig
from game.inventory.items import add_item, generate_component
from game.progression.leveling import add_xp
from game.progression.profile import PlayerProfile

ACTIVE, SUCCESS, FAILED = "active", "success", "failed"


class MissionRuntime:
    def __init__(self, mission: dict):
        self.cfg = mission
        self.type = mission["type"]
        self.params = mission.get("params", {})
        self.state = ACTIVE
        self.fail_reason = ""
        self.kills = 0
        self.pickups = 0
        self.timer = 0.0
        self.escort_progress = 0.0
        self.fleet_cleared = False

    # --- sucesos -------------------------------------------------------------
    def on_enemy_killed(self, enemy_type: str, elite: bool = False, boss: bool = False) -> None:
        if self.state != ACTIVE:
            return
        if self.type == "destroy_count":
            wanted = self.params.get("enemy")
            if wanted is None or wanted == enemy_type:
                self.kills += 1
                if self.kills >= int(self.params["count"]):
                    self.succeed()
        elif self.type == "eliminate_elite":
            if elite and enemy_type == self.params.get("enemy"):
                self.succeed()
        elif self.type == "boss" and boss:
            self.succeed()

    def on_pickup(self) -> None:
        if self.state == ACTIVE and self.type == "recover_materials":
            self.pickups += 1
            if self.pickups >= int(self.params["count"]):
                self.succeed()

    def on_fleet_cleared(self) -> None:
        if self.state == ACTIVE and self.type == "destroy_fleet":
            self.fleet_cleared = True
            self.succeed()

    def on_ally_destroyed(self, name: str) -> None:
        if self.state == ACTIVE and self.type in ("defend_station", "escort"):
            self.fail(f"{name} ha sido destruido")

    def on_escort_progress(self, travelled: float) -> None:
        if self.state == ACTIVE and self.type == "escort":
            self.escort_progress = travelled
            if travelled >= float(self.params["distance"]):
                self.succeed()

    def on_player_destroyed(self) -> None:
        self.fail("Tu nave ha sido destruida")

    def update(self, dt: float) -> None:
        if self.state != ACTIVE:
            return
        self.timer += dt
        if self.type in ("defend_station", "survive_time") and self.timer >= float(self.params["duration"]):
            self.succeed()

    def succeed(self) -> None:
        if self.state == ACTIVE:
            self.state = SUCCESS

    def fail(self, reason: str) -> None:
        if self.state == ACTIVE:
            self.state = FAILED
            self.fail_reason = reason

    # --- presentación --------------------------------------------------------
    def objective_text(self) -> str:
        t, p = self.type, self.params
        if t == "destroy_count":
            return f"Destruye objetivos: {self.kills}/{p['count']}"
        if t == "destroy_fleet":
            return "Destruye toda la flota enemiga"
        if t == "defend_station":
            return f"Defiende la estación: {max(0, p['duration'] - self.timer):.0f} s"
        if t == "survive_time":
            return f"Sobrevive: {max(0, p['duration'] - self.timer):.0f} s"
        if t == "escort":
            return f"Escolta al carguero: {self.escort_progress:.0f}/{p['distance']} m"
        if t == "recover_materials":
            return f"Recupera contenedores: {self.pickups}/{p['count']}"
        if t == "eliminate_elite":
            return "Elimina a la nave de élite (marcada en dorado)"
        if t == "boss":
            return "Derrota al jefe"
        return ""

    @property
    def keeps_spawning(self) -> bool:
        """Las misiones por tiempo o escolta siguen recibiendo enemigos."""
        return bool(self.cfg.get("loop_waves"))


class WaveDirector:
    """Decide cuándo entra cada oleada y genera refuerzos."""

    def __init__(self, waves: list[dict], reinforce_at: int = 0, loop: bool = False):
        self.waves = waves
        self.reinforce_at = int(reinforce_at)
        self.loop = loop
        self.index = 0
        self.wait = None  # cuenta atrás de la oleada pendiente
        self.stopped = False
        self.waves_spawned = 0

    @property
    def all_spawned(self) -> bool:
        return not self.loop and self.index >= len(self.waves)

    def stop(self) -> None:
        self.stopped = True

    def update(self, dt: float, alive: int) -> list[dict]:
        """Devuelve grupos ``{"type", "count", "elite"}`` para generar ahora."""
        if self.stopped or not self.waves or self.all_spawned:
            return []
        first = self.waves_spawned == 0
        if self.wait is None:
            if first or alive <= self.reinforce_at:
                self.wait = float(self.waves[self.index].get("delay", 0))
            else:
                return []
        self.wait -= dt
        if self.wait > 0:
            return []
        wave = self.waves[self.index]
        groups = [{"type": t, "count": int(n), "elite": False} for t, n in wave.get("enemies", {}).items()]
        groups += [{"type": t, "count": int(n), "elite": True} for t, n in wave.get("elite", {}).items()]
        self.index += 1
        self.waves_spawned += 1
        if self.loop and self.index >= len(self.waves):
            self.index = 0
        self.wait = None
        return groups


# --- recompensas ---------------------------------------------------------------
def empty_rewards() -> dict:
    return {"xp": 0, "credits": 0, "materials": {}, "blueprints": [], "items": []}


def merge_rewards(total: dict, extra: dict) -> dict:
    total["xp"] += int(extra.get("xp", 0))
    total["credits"] += int(extra.get("credits", 0))
    for mat, amount in extra.get("materials", {}).items():
        total["materials"][mat] = total["materials"].get(mat, 0) + int(amount)
    total["blueprints"] += [b for b in extra.get("blueprints", []) if b not in total["blueprints"]]
    total["items"] += list(extra.get("items", []))
    return total


def kill_rewards(enemy_cfg: dict, galaxy: dict, elite: bool, rng: random.Random, config: GameConfig) -> dict:
    mult = galaxy["difficulty"]["reward_mult"] * (config.elite["reward_mult"] if elite else 1.0)
    drops = config.economy["drops"]
    out = empty_rewards()
    out["xp"] = int(round(enemy_cfg["rewards"]["xp"] * mult))
    out["credits"] = int(round(enemy_cfg["rewards"]["credits"] * mult))
    if rng.random() < drops["material_chance"] or elite:
        low, high = drops["material_amount"]
        out["materials"][galaxy["material"]] = rng.randint(low, high) * (2 if elite else 1)
    chance = drops["elite_component_chance"] if elite else drops["component_chance"]
    if rng.random() < chance:
        out["items"].append(generate_component(rng, config, tier=int(galaxy["tier"])))
    return out


def mission_rewards(galaxy: dict, mission: dict, rng: random.Random, config: GameConfig,
                    first_time: bool = True) -> dict:
    """Recompensa por completar la misión (los planos solo la primera vez)."""
    sources = [mission.get("rewards", {})]
    if mission["type"] == "boss":
        sources.append(config.bosses[mission["params"]["boss"]].get("rewards", {}))
    out = empty_rewards()
    repeat = 1.0 if first_time else 0.4
    for src in sources:
        out["xp"] += int(src.get("xp", 0) * repeat)
        out["credits"] += int(src.get("credits", 0) * repeat)
        for mat, amount in src.get("materials", {}).items():
            out["materials"][mat] = out["materials"].get(mat, 0) + int(amount * repeat)
        if first_time and src.get("blueprint"):
            out["blueprints"].append(src["blueprint"])
        if src.get("item_rarity") and first_time:
            out["items"].append(generate_component(rng, config, tier=int(galaxy["tier"]), rarity=src["item_rarity"]))
    return out


def apply_rewards(profile: PlayerProfile, rewards: dict, config: GameConfig) -> dict:
    """Aplica recompensas al perfil. Devuelve niveles ganados y objetos descartados."""
    profile.credits += int(rewards["credits"])
    for mat, amount in rewards["materials"].items():
        profile.add_material(mat, amount)
    for blueprint in rewards["blueprints"]:
        if blueprint not in profile.blueprints:
            profile.blueprints.append(blueprint)
    discarded = [item for item in rewards["items"] if not add_item(profile, item, config)]
    levels = add_xp(profile, rewards["xp"], config)
    return {"levels": levels, "discarded": discarded}


def complete_mission(profile: PlayerProfile, galaxy: dict, mission: dict, config: GameConfig) -> dict:
    """Marca la misión como completada y desbloquea la siguiente galaxia si toca."""
    events = {"galaxy_unlocked": None, "campaign_complete": False, "first_time": False}
    if mission["id"] not in profile.completed_missions:
        profile.completed_missions.append(mission["id"])
        events["first_time"] = True
    profile.stats["missions"] = profile.stats.get("missions", 0) + 1
    if mission["type"] == "boss":
        profile.stats["bosses"] = profile.stats.get("bosses", 0) + 1
    if mission["id"] == galaxy["missions"][0]["id"]:
        profile.flags["workshop_unlocked"] = True
        profile.flags["tutorial_done"] = True
    mains_done = all(m["id"] in profile.completed_missions for m in galaxy["missions"] if m.get("main"))
    if mains_done:
        index = config.galaxy_index(galaxy["id"])
        if index + 1 < len(config.galaxies):
            nxt = config.galaxies[index + 1]["id"]
            if nxt not in profile.unlocked_galaxies:
                profile.unlocked_galaxies.append(nxt)
                events["galaxy_unlocked"] = nxt
        elif mission.get("params", {}).get("final"):
            events["campaign_complete"] = True
            profile.flags["campaign_complete"] = True
    return events
