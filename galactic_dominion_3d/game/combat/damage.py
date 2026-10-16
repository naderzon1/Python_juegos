"""Modelo de daño: escudos que absorben primero, casco y golpes críticos.

Cada impacto tiene multiplicadores contra escudo y contra casco (el plasma
destroza cascos, la energía consume escudos). El escudo se regenera solo
cuando la nave lleva ``shield_delay`` segundos sin recibir daño.
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class DamageInfo:
    amount: float
    shield_mult: float = 1.0
    hull_mult: float = 1.0
    crit: bool = False
    source: object | None = None


@dataclass
class DamageResult:
    shield_damage: float = 0.0
    hull_damage: float = 0.0
    shield_broken: bool = False
    destroyed: bool = False
    crit: bool = False


def roll_damage(base: float, mult: float, crit_chance: float, crit_mult: float,
                rng: random.Random | None = None) -> tuple[float, bool]:
    rng = rng or random
    crit = rng.random() < max(0.0, min(1.0, crit_chance))
    amount = base * mult * (crit_mult if crit else 1.0)
    return amount, crit


class Durability:
    def __init__(self, max_hull: float, max_shield: float = 0.0, shield_regen: float = 0.0,
                 shield_delay: float = 3.0, armor: float = 1.0):
        self.max_hull = float(max_hull)
        self.hull = float(max_hull)
        self.max_shield = float(max_shield)
        self.shield = float(max_shield)
        self.shield_regen = float(shield_regen)
        self.shield_delay = float(shield_delay)
        self.armor = float(armor)  # multiplicador de daño recibido (1 = normal)
        self.since_hit = 999.0
        self.invulnerable = False

    @property
    def destroyed(self) -> bool:
        return self.hull <= 0

    @property
    def hull_ratio(self) -> float:
        return max(0.0, self.hull / self.max_hull) if self.max_hull else 0.0

    @property
    def shield_ratio(self) -> float:
        return max(0.0, self.shield / self.max_shield) if self.max_shield else 0.0

    def apply(self, info: DamageInfo) -> DamageResult:
        result = DamageResult(crit=info.crit)
        if self.destroyed or self.invulnerable or info.amount <= 0:
            return result
        self.since_hit = 0.0
        raw = info.amount * self.armor
        if self.shield > 0:
            shield_dmg = raw * info.shield_mult
            if shield_dmg <= self.shield:
                self.shield -= shield_dmg
                result.shield_damage = shield_dmg
                return result
            # el escudo cae: el resto (en daño bruto) pasa al casco
            absorbed_raw = self.shield / max(info.shield_mult, 1e-6)
            result.shield_damage = self.shield
            self.shield = 0.0
            result.shield_broken = True
            raw = max(0.0, raw - absorbed_raw)
        hull_dmg = raw * info.hull_mult
        self.hull = max(0.0, self.hull - hull_dmg)
        result.hull_damage = hull_dmg
        result.destroyed = self.destroyed
        return result

    def update(self, dt: float) -> None:
        self.since_hit += dt
        if self.destroyed:
            return
        if self.since_hit >= self.shield_delay and self.shield < self.max_shield:
            self.shield = min(self.max_shield, self.shield + self.shield_regen * dt)

    def repair(self) -> None:
        self.hull = self.max_hull
        self.shield = self.max_shield
