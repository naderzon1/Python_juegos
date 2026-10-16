"""Objetos del inventario: componentes de nave con rareza.

Un componente mejora una estadística de la nave mientras está equipado. Su
valor depende de la estadística, de la rareza (común → legendaria) y del
nivel de la galaxia donde se consiguió.
"""
from __future__ import annotations

import random
import uuid

from game.core.config import GameConfig
from game.progression.profile import PlayerProfile

RARITY_ORDER = ("common", "uncommon", "rare", "epic", "legendary")


def roll_rarity(rng: random.Random, config: GameConfig, tier: int = 1, minimum: str | None = None) -> str:
    rarities = config.economy["rarities"]
    bonus = config.economy["drops"]["tier_rarity_bonus"] * (tier - 1)
    weights = []
    for index, rid in enumerate(RARITY_ORDER):
        weight = rarities[rid]["weight"] * (1 + bonus * index)
        if minimum and index < RARITY_ORDER.index(minimum):
            weight = 0
        weights.append(weight)
    return rng.choices(RARITY_ORDER, weights=weights, k=1)[0]


def generate_component(rng: random.Random, config: GameConfig, tier: int = 1, rarity: str | None = None) -> dict:
    rarity = rarity or roll_rarity(rng, config, tier)
    stat = rng.choice(sorted(config.economy["components"]))
    comp = config.economy["components"][stat]
    mult = config.economy["rarities"][rarity]["mult"]
    value = round(comp["base"] * mult * (1 + 0.25 * (tier - 1)) * rng.uniform(0.9, 1.1), 4)
    return {
        "id": uuid.uuid4().hex[:12],
        "kind": "component",
        "name": comp["name"],
        "stat": stat,
        "value": value,
        "rarity": rarity,
        "tier": tier,
    }


def describe_item(item: dict, config: GameConfig) -> str:
    comp = config.economy["components"].get(item.get("stat"), {})
    rarity = config.economy["rarities"].get(item.get("rarity"), {}).get("name", item.get("rarity", "?"))
    value = float(item.get("value", 0))
    if comp.get("unit") == "%":
        amount = f"+{value * 100:.1f}%"
    else:
        amount = f"+{value * 100:.1f}% crítico" if item.get("stat") == "crit_bonus" else f"+{value:.2f}"
    return f"{item.get('name', 'Componente')} [{rarity}] T{item.get('tier', 1)}  {amount}"


def sell_value(item: dict, config: GameConfig) -> int:
    base = config.economy["rarities"].get(item.get("rarity"), {}).get("sell", 10)
    return int(base * (1 + 0.3 * (int(item.get("tier", 1)) - 1)))


def add_item(profile: PlayerProfile, item: dict, config: GameConfig) -> bool:
    if len(profile.inventory) >= int(config.economy["inventory_limit"]):
        return False
    profile.inventory.append(item)
    return True


def equip_component(profile: PlayerProfile, item_id: str, slots: int) -> tuple[bool, str]:
    item = profile.item(item_id)
    if item is None:
        return False, "El objeto no existe"
    if item_id in profile.equipped_components:
        return False, "Ya está equipado"
    if len(profile.equipped_components) >= slots:
        return False, f"Sin ranuras libres ({slots})"
    profile.equipped_components.append(item_id)
    return True, "Equipado"


def unequip_component(profile: PlayerProfile, item_id: str) -> bool:
    if item_id in profile.equipped_components:
        profile.equipped_components.remove(item_id)
        return True
    return False


def sell_item(profile: PlayerProfile, item_id: str, config: GameConfig) -> int:
    item = profile.item(item_id)
    if item is None:
        return 0
    unequip_component(profile, item_id)
    profile.inventory.remove(item)
    value = sell_value(item, config)
    profile.credits += value
    return value
