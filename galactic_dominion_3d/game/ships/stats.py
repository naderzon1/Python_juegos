"""Cálculo de las estadísticas finales de la nave del jugador.

Orden de aplicación: valores base de la nave (``ships.json``) → mejoras del
taller (``upgrades.json``) → bonificación por nivel del piloto → etapa de
evolución de la nave (Mk I-V, según el nivel) → componentes equipados.
Así cada compra y cada nivel modifican el combate de verdad.

Notas de unidades: ``accel`` es la rapidez (1/s) con la que la velocidad se
acerca a la deseada; ``turn_rate`` y ``roll_rate`` están en grados/segundo.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from game.core.config import GameConfig
from game.progression.evolution import tier_for_level
from game.progression.profile import PlayerProfile

PERCENT_DEFAULT_STATS = {"damage_mult", "drone_damage_mult", "crit_bonus", "drone_count", "missile_capacity"}


@dataclass
class ShipStats:
    max_hull: float = 100
    max_shield: float = 50
    shield_regen: float = 10
    shield_delay: float = 3
    max_energy: float = 100
    energy_regen: float = 20
    max_speed: float = 70
    boost_mult: float = 1.8
    boost_cost: float = 22
    accel: float = 2.4
    turn_rate: float = 90
    roll_rate: float = 150
    missile_capacity: float = 8
    damage_mult: float = 1.0
    crit_bonus: float = 0.0
    lock_range: float = 1600
    lock_time: float = 0.9
    drone_count: float = 2
    drone_damage_mult: float = 1.0
    component_slots: float = 2
    radius: float = 5
    tier: int = 1

    def to_dict(self) -> dict:
        return asdict(self)


def base_stats(ship_cfg: dict) -> ShipStats:
    return ShipStats(
        max_hull=ship_cfg["hull"], max_shield=ship_cfg["shield"], shield_regen=ship_cfg["shield_regen"],
        shield_delay=ship_cfg["shield_delay"], max_energy=ship_cfg["energy"], energy_regen=ship_cfg["energy_regen"],
        max_speed=ship_cfg["max_speed"], boost_mult=ship_cfg["boost_mult"], boost_cost=ship_cfg["boost_cost"],
        accel=ship_cfg["accel"], turn_rate=ship_cfg["turn_rate"], roll_rate=ship_cfg["roll_rate"],
        missile_capacity=ship_cfg["missile_capacity"], component_slots=ship_cfg["component_slots"],
        radius=ship_cfg.get("radius", 5),
    )


def _apply(stats: ShipStats, stat: str, amount: float, mode: str, base: ShipStats) -> None:
    current = getattr(stats, stat)
    if mode == "percent":
        setattr(stats, stat, current + getattr(base, stat) * amount)
    else:
        setattr(stats, stat, current + amount)


def compute_ship_stats(profile: PlayerProfile, config: GameConfig) -> ShipStats:
    ship_cfg = config.ships.get(profile.ship) or config.ships[config.start_ship]
    base = base_stats(ship_cfg)
    stats = base_stats(ship_cfg)
    for uid, level in profile.upgrades.items():
        upg = config.upgrades.get(uid)
        if not upg or level <= 0:
            continue
        for effect in upg["effects"]:
            _apply(stats, effect["stat"], effect["per_level"] * level, effect.get("mode", "add"), base)
    bonus = config.economy["pilot_level"]["bonus_per_level"]
    for stat, per_level in bonus.items():
        mode = "add" if stat in PERCENT_DEFAULT_STATS else "percent"
        _apply(stats, stat, per_level * (profile.level - 1), mode, base)
    tier = tier_for_level(profile.level, config)
    stats.tier = tier
    for stat, per_tier in config.economy.get("ship_evolution", {}).get("per_tier", {}).items():
        mode = "add" if stat in PERCENT_DEFAULT_STATS else "percent"
        _apply(stats, stat, per_tier * (tier - 1), mode, base)
    for item_id in profile.equipped_components:
        item = profile.item(item_id)
        if not item:
            continue
        stat = item.get("stat")
        if stat in config.economy["components"]:
            mode = "add" if stat in PERCENT_DEFAULT_STATS else "percent"
            _apply(stats, stat, float(item.get("value", 0)), mode, base)
    stats.lock_time = max(0.25, stats.lock_time)
    stats.boost_cost = max(5.0, stats.boost_cost)
    stats.drone_count = int(stats.drone_count)
    stats.missile_capacity = int(stats.missile_capacity)
    stats.component_slots = int(stats.component_slots)
    return stats
