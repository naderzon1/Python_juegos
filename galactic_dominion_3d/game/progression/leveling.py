"""Experiencia y niveles del piloto."""
from __future__ import annotations

from game.core.config import GameConfig
from game.progression.profile import PlayerProfile


def xp_for_next_level(level: int, config: GameConfig) -> int:
    """Experiencia necesaria para pasar de ``level`` a ``level + 1``."""
    cfg = config.economy["pilot_level"]
    return int(round(cfg["xp_base"] * level ** cfg["xp_exponent"]))


def add_xp(profile: PlayerProfile, amount: int, config: GameConfig) -> list[int]:
    """Suma experiencia y devuelve la lista de niveles alcanzados."""
    max_level = int(config.economy["pilot_level"]["max_level"])
    profile.xp += max(0, int(amount))
    reached: list[int] = []
    while profile.level < max_level and profile.xp >= xp_for_next_level(profile.level, config):
        profile.xp -= xp_for_next_level(profile.level, config)
        profile.level += 1
        reached.append(profile.level)
    if profile.level >= max_level:
        profile.xp = min(profile.xp, xp_for_next_level(max_level, config))
    return reached


def level_progress(profile: PlayerProfile, config: GameConfig) -> float:
    return min(1.0, profile.xp / max(1, xp_for_next_level(profile.level, config)))
