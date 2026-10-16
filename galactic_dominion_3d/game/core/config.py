"""Carga y validación de la configuración externa (carpeta ``config/``).

Toda la información de diseño (armas, enemigos, galaxias, naves, mejoras y
economía) vive en archivos JSON. ``GameConfig`` los carga, comprueba que las
referencias cruzadas sean válidas (por ejemplo, que una misión no use un
enemigo inexistente) y ofrece accesos cómodos al resto del juego.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from game.core.paths import CONFIG_DIR

CONFIG_FILES = ("weapons", "enemies", "galaxies", "ships", "upgrades", "economy", "graphics", "controls", "audio")

WEAPON_FIELDS = ("name", "slot", "kind", "damage", "fire_rate", "range", "projectile_speed", "energy_cost",
                 "crit_chance", "shield_mult", "hull_mult", "explosion_radius", "tech_level", "rarity", "color")
WEAPON_SLOTS = ("primary", "secondary", "special")
WEAPON_KINDS = ("projectile", "beam", "missile", "drones", "pulse", "torpedo")
MISSION_TYPES = ("destroy_count", "destroy_fleet", "defend_station", "escort", "recover_materials",
                 "survive_time", "eliminate_elite", "boss")
SHIP_STATS = ("max_hull", "max_shield", "shield_regen", "shield_delay", "max_energy", "energy_regen", "max_speed",
              "boost_mult", "boost_cost", "accel", "turn_rate", "roll_rate", "missile_capacity", "damage_mult",
              "crit_bonus", "lock_range", "lock_time", "drone_count", "drone_damage_mult", "component_slots")


class ConfigError(Exception):
    """Error de configuración con un mensaje legible para el usuario."""


def load_json(path: Path) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"Falta el archivo de configuración {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path.name} no es un JSON válido (línea {exc.lineno}: {exc.msg})") from exc


class GameConfig:
    def __init__(self, config_dir: Path = CONFIG_DIR):
        self.dir = Path(config_dir)
        raw = {name: load_json(self.dir / f"{name}.json") for name in CONFIG_FILES}
        self.raw = raw
        self.crit_multiplier: float = float(raw["weapons"].get("crit_multiplier", 2.0))
        self.weapons: dict[str, dict] = raw["weapons"]["weapons"]
        self.enemies: dict[str, dict] = raw["enemies"]["enemies"]
        self.bosses: dict[str, dict] = raw["enemies"]["bosses"]
        self.elite: dict = raw["enemies"]["elite"]
        self.galaxies: list[dict] = raw["galaxies"]["galaxies"]
        self.ships: dict[str, dict] = raw["ships"]["ships"]
        self.start_ship: str = raw["ships"]["start_ship"]
        self.upgrades_root: dict = raw["upgrades"]
        self.upgrades: dict[str, dict] = raw["upgrades"]["upgrades"]
        self.economy: dict = raw["economy"]
        self.graphics: dict = raw["graphics"]
        self.controls: dict = raw["controls"]
        self.audio: dict = raw["audio"]
        self.validate()

    # --- accesos -------------------------------------------------------------
    def galaxy(self, galaxy_id: str) -> dict:
        for galaxy in self.galaxies:
            if galaxy["id"] == galaxy_id:
                return galaxy
        raise KeyError(galaxy_id)

    def galaxy_index(self, galaxy_id: str) -> int:
        return [g["id"] for g in self.galaxies].index(galaxy_id)

    def mission(self, mission_id: str) -> tuple[dict, dict]:
        for galaxy in self.galaxies:
            for mission in galaxy["missions"]:
                if mission["id"] == mission_id:
                    return galaxy, mission
        raise KeyError(mission_id)

    def player_weapons(self) -> dict[str, dict]:
        return {k: v for k, v in self.weapons.items() if v.get("player_usable")}

    def material_name(self, material_id: str) -> str:
        return self.economy["materials"].get(material_id, material_id)

    # --- validación ----------------------------------------------------------
    def validate(self) -> None:
        errors: list[str] = []
        for wid, w in self.weapons.items():
            missing = [f for f in WEAPON_FIELDS if f not in w]
            if missing:
                errors.append(f"Arma '{wid}': faltan campos {missing}")
            if w.get("slot") not in WEAPON_SLOTS:
                errors.append(f"Arma '{wid}': ranura inválida {w.get('slot')}")
            if w.get("kind") not in WEAPON_KINDS:
                errors.append(f"Arma '{wid}': tipo inválido {w.get('kind')}")
            if w.get("rarity") not in self.economy["rarities"]:
                errors.append(f"Arma '{wid}': rareza desconocida {w.get('rarity')}")
            if float(w.get("fire_rate", 0)) <= 0:
                errors.append(f"Arma '{wid}': fire_rate debe ser mayor que 0")
        for eid, e in {**self.enemies, **self.bosses}.items():
            for wid in e.get("weapons", []):
                if wid not in self.weapons:
                    errors.append(f"Enemigo '{eid}': arma inexistente '{wid}'")
        for bid, b in self.bosses.items():
            if not b.get("phases"):
                errors.append(f"Jefe '{bid}': necesita al menos una fase")
            bp = b.get("rewards", {}).get("blueprint")
            if bp and bp not in self.weapons:
                errors.append(f"Jefe '{bid}': plano de arma inexistente '{bp}'")
        mission_ids: set[str] = set()
        for galaxy in self.galaxies:
            for key in ("id", "name", "environment", "missions", "difficulty", "material"):
                if key not in galaxy:
                    errors.append(f"Galaxia '{galaxy.get('id', '?')}': falta '{key}'")
            if galaxy.get("material") not in self.economy["materials"]:
                errors.append(f"Galaxia '{galaxy.get('id')}': material desconocido")
            if not any(m.get("type") == "boss" and m.get("main") for m in galaxy.get("missions", [])):
                errors.append(f"Galaxia '{galaxy.get('id')}': necesita una misión principal de jefe")
            local = {m["id"] for m in galaxy.get("missions", [])}
            for mission in galaxy.get("missions", []):
                mid = mission.get("id")
                if mid in mission_ids:
                    errors.append(f"Misión duplicada '{mid}'")
                mission_ids.add(mid)
                if mission.get("type") not in MISSION_TYPES:
                    errors.append(f"Misión '{mid}': tipo inválido {mission.get('type')}")
                for req in mission.get("requires", []):
                    if req not in local:
                        errors.append(f"Misión '{mid}': requisito '{req}' no existe en la galaxia")
                for wave in mission.get("waves", []):
                    for group in ("enemies", "elite"):
                        for etype in wave.get(group, {}):
                            if etype not in self.enemies:
                                errors.append(f"Misión '{mid}': enemigo inexistente '{etype}'")
                if mission.get("type") == "boss" and mission.get("params", {}).get("boss") not in self.bosses:
                    errors.append(f"Misión '{mid}': jefe inexistente")
                bp = mission.get("rewards", {}).get("blueprint")
                if bp and bp not in self.weapons:
                    errors.append(f"Misión '{mid}': plano de arma inexistente '{bp}'")
        for uid, upg in self.upgrades.items():
            for effect in upg.get("effects", []):
                if effect.get("stat") not in SHIP_STATS:
                    errors.append(f"Mejora '{uid}': estadística desconocida '{effect.get('stat')}'")
        for stat in self.economy["components"]:
            if stat not in SHIP_STATS:
                errors.append(f"Componente: estadística desconocida '{stat}'")
        if self.start_ship not in self.ships:
            errors.append("La nave inicial no existe")
        start = self.economy["start"]
        for wid in start["weapons"]:
            if wid not in self.weapons:
                errors.append(f"Arma inicial inexistente '{wid}'")
        evo = self.economy.get("ship_evolution")
        if evo:
            levels = [int(t["level"]) for t in evo.get("tiers", [])]
            if not levels or levels[0] != 1 or levels != sorted(set(levels)):
                errors.append("ship_evolution: las etapas deben empezar en el nivel 1 y ser crecientes")
            for stat in evo.get("per_tier", {}):
                if stat not in SHIP_STATS:
                    errors.append(f"ship_evolution: estadística desconocida '{stat}'")
        if self.graphics.get("preset") not in self.graphics.get("presets", {}):
            errors.append("Preajuste gráfico por defecto inexistente")
        if errors:
            raise ConfigError("Configuración inválida:\n- " + "\n- ".join(errors))
