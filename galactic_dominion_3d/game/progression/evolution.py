"""Evolución automática de la nave con el nivel del piloto (Mk I → Mk V).

Al subir de nivel la nave cambia de etapa: más casco y escudo, más daño,
disparos más grandes y numerosos, un sonido más grave y potente y un modelo
3D con más piezas. Los umbrales y bonificaciones están en
``config/economy.json → ship_evolution``.
"""
from __future__ import annotations

from dataclasses import dataclass

from game.core.config import GameConfig


@dataclass
class Evolution:
    tier: int            # 1..N
    name: str            # "Mk III"
    summary: str
    next_level: int | None
    extra_projectiles: int
    shot_damage: float   # multiplicador por proyectil cuando hay disparo múltiple
    bolt_size: float     # multiplicador del tamaño visual de los proyectiles
    sound_rate: float    # velocidad de reproducción (menor = más grave)
    sound_volume: float  # multiplicador de volumen


def tier_for_level(level: int, config: GameConfig) -> int:
    tiers = config.economy["ship_evolution"]["tiers"]
    tier = 1
    for i, info in enumerate(tiers):
        if level >= int(info["level"]):
            tier = i + 1
    return tier


def evolution(level: int, config: GameConfig) -> Evolution:
    cfg = config.economy["ship_evolution"]
    tiers = cfg["tiers"]
    tier = tier_for_level(level, config)
    info = tiers[tier - 1]
    extra = 0
    for min_tier, amount in cfg["extra_projectiles"].items():
        if tier >= int(min_tier):
            extra = max(extra, int(amount))
    steps = tier - 1
    return Evolution(
        tier=tier,
        name=info["name"],
        summary=info["summary"],
        next_level=int(tiers[tier]["level"]) if tier < len(tiers) else None,
        extra_projectiles=extra,
        shot_damage=float(cfg["multishot_damage"]) if extra else 1.0,
        bolt_size=1.0 + float(cfg["bolt_size_per_tier"]) * steps,
        sound_rate=max(0.5, 1.0 + float(cfg["sound_rate_per_tier"]) * steps),
        sound_volume=1.0 + float(cfg["sound_volume_per_tier"]) * steps,
    )


def tier_changes(old_level: int, new_level: int, config: GameConfig) -> list[Evolution]:
    """Etapas alcanzadas al pasar de ``old_level`` a ``new_level`` (para avisar al jugador)."""
    old, new = tier_for_level(old_level, config), tier_for_level(new_level, config)
    return [evolution(int(config.economy["ship_evolution"]["tiers"][t - 1]["level"]), config)
            for t in range(old + 1, new + 1)]
