"""Definición y estado de las armas (sin dependencias del motor).

``WeaponState`` lleva la cadencia, la recarga y la munición. El disparo real
(crear proyectiles, rayos o drones) lo hace ``combat.projectiles`` usando los
parámetros de ``WeaponDef``.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WeaponDef:
    id: str
    name: str
    slot: str
    kind: str
    damage: float
    fire_rate: float
    range: float
    projectile_speed: float
    energy_cost: float
    cooldown: float
    crit_chance: float
    spread_deg: float
    projectiles: int
    shield_mult: float
    hull_mult: float
    explosion_radius: float
    tech_level: int
    rarity: str
    color: tuple
    size: float = 1.0
    sound: str = ""
    turn_rate: float = 0.0
    lifetime: float = 3.0
    duration: float = 0.0
    description: str = ""
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_config(cls, weapon_id: str, data: dict) -> "WeaponDef":
        known = set(cls.__dataclass_fields__) - {"id", "extra"}
        kwargs = {k: data[k] for k in known if k in data}
        kwargs.setdefault("cooldown", 0.0)
        kwargs.setdefault("spread_deg", 0.0)
        kwargs.setdefault("projectiles", 1)
        if "lifetime" not in data and data.get("projectile_speed"):
            kwargs["lifetime"] = data["range"] / data["projectile_speed"]
        kwargs["color"] = tuple(data["color"])
        return cls(id=weapon_id, extra={k: v for k, v in data.items() if k not in known}, **kwargs)

    @property
    def interval(self) -> float:
        """Tiempo mínimo entre disparos (cadencia o recarga, lo que sea mayor)."""
        return max(1.0 / self.fire_rate, self.cooldown)

    @property
    def uses_ammo(self) -> bool:
        return self.kind == "missile"


class WeaponState:
    def __init__(self, definition: WeaponDef, ammo: int | None = None):
        self.d = definition
        self.timer = 0.0
        self.ammo = ammo

    def update(self, dt: float) -> None:
        self.timer = max(0.0, self.timer - dt)

    @property
    def ready(self) -> bool:
        return self.timer <= 0.0

    @property
    def cooldown_ratio(self) -> float:
        return self.timer / self.d.interval if self.d.interval > 0 else 0.0

    def can_fire(self, energy: float) -> bool:
        if not self.ready:
            return False
        if self.d.uses_ammo and self.ammo is not None and self.ammo <= 0:
            return False
        return energy >= self.d.energy_cost

    def fire(self) -> None:
        self.timer = self.d.interval
        if self.d.uses_ammo and self.ammo is not None:
            self.ammo -= 1
