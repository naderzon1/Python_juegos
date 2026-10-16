"""Taller, armería y astillero: precios, requisitos y compras.

Todos los precios y requisitos salen de ``upgrades.json``, ``weapons.json`` y
``ships.json``. Las funciones ``can_*`` devuelven ``(posible, motivo)`` para
que la interfaz explique por qué algo no se puede comprar.
"""
from __future__ import annotations

from game.core.config import GameConfig
from game.progression.profile import PlayerProfile


def galaxies_unlocked(profile: PlayerProfile) -> int:
    return len(profile.unlocked_galaxies)


# --- mejoras ---------------------------------------------------------------
def upgrade_material(level: int, config: GameConfig) -> str:
    material = config.upgrades_root["material_tiers"][0][1]
    for min_level, mat in config.upgrades_root["material_tiers"]:
        if level >= min_level:
            material = mat
    return material


def required_galaxies_for_upgrade(level: int, config: GameConfig) -> int:
    required = 1
    for min_level, galaxies in config.upgrades_root["tech_gates"].items():
        if level >= int(min_level):
            required = max(required, int(galaxies))
    return required


def upgrade_cost(upgrade_id: str, target_level: int, config: GameConfig) -> tuple[int, dict]:
    """Coste para subir la mejora a ``target_level`` (1..max)."""
    upg = config.upgrades[upgrade_id]
    credits = int(round(upg["base_cost"] * upg["cost_growth"] ** (target_level - 1)))
    material = upgrade_material(target_level, config)
    amount = int(upg["material_base"] * target_level)
    return credits, {material: amount}


def can_buy_upgrade(profile: PlayerProfile, upgrade_id: str, config: GameConfig) -> tuple[bool, str]:
    if upgrade_id not in config.upgrades:
        return False, "Mejora desconocida"
    current = int(profile.upgrades.get(upgrade_id, 0))
    upg = config.upgrades[upgrade_id]
    if current >= upg["max_level"]:
        return False, "Nivel máximo"
    target = current + 1
    needed = required_galaxies_for_upgrade(target, config)
    if galaxies_unlocked(profile) < needed:
        return False, f"Requiere tecnología de la galaxia {needed}"
    credits, materials = upgrade_cost(upgrade_id, target, config)
    if profile.credits < credits:
        return False, f"Faltan {credits - profile.credits} créditos"
    for mat, amount in materials.items():
        if profile.material(mat) < amount:
            return False, f"Faltan {amount - profile.material(mat)} de {config.material_name(mat)}"
    return True, "Disponible"


def buy_upgrade(profile: PlayerProfile, upgrade_id: str, config: GameConfig) -> tuple[bool, str]:
    ok, reason = can_buy_upgrade(profile, upgrade_id, config)
    if not ok:
        return False, reason
    target = int(profile.upgrades.get(upgrade_id, 0)) + 1
    credits, materials = upgrade_cost(upgrade_id, target, config)
    profile.credits -= credits
    for mat, amount in materials.items():
        profile.materials[mat] = profile.material(mat) - amount
    profile.upgrades[upgrade_id] = target
    return True, f"{config.upgrades[upgrade_id]['name']} nivel {target}"


# --- armas ------------------------------------------------------------------
def can_unlock_weapon(profile: PlayerProfile, weapon_id: str, config: GameConfig) -> tuple[bool, str]:
    weapon = config.weapons.get(weapon_id)
    if not weapon or not weapon.get("player_usable"):
        return False, "Arma no disponible"
    if weapon_id in profile.unlocked_weapons:
        return False, "Ya desbloqueada"
    unlock = weapon.get("unlock", {})
    if unlock.get("blueprint") and weapon_id not in profile.blueprints:
        return False, "Necesitas el plano (se obtiene en misiones y jefes)"
    if galaxies_unlocked(profile) < int(weapon["tech_level"]):
        return False, f"Requiere tecnología de la galaxia {weapon['tech_level']}"
    cost = int(unlock.get("credits", 0))
    if profile.credits < cost:
        return False, f"Faltan {cost - profile.credits} créditos"
    return True, "Disponible"


def unlock_weapon(profile: PlayerProfile, weapon_id: str, config: GameConfig) -> tuple[bool, str]:
    ok, reason = can_unlock_weapon(profile, weapon_id, config)
    if not ok:
        return False, reason
    profile.credits -= int(config.weapons[weapon_id].get("unlock", {}).get("credits", 0))
    profile.unlocked_weapons.append(weapon_id)
    slot = config.weapons[weapon_id]["slot"]
    if not profile.loadout.get(slot):
        profile.loadout[slot] = weapon_id
    return True, f"{config.weapons[weapon_id]['name']} desbloqueado"


def equip_weapon(profile: PlayerProfile, weapon_id: str, config: GameConfig) -> tuple[bool, str]:
    if weapon_id not in profile.unlocked_weapons:
        return False, "Arma bloqueada"
    slot = config.weapons[weapon_id]["slot"]
    profile.loadout[slot] = weapon_id
    return True, f"Equipado en ranura {slot}"


# --- naves ------------------------------------------------------------------
def can_buy_ship(profile: PlayerProfile, ship_id: str, config: GameConfig) -> tuple[bool, str]:
    ship = config.ships.get(ship_id)
    if not ship:
        return False, "Nave desconocida"
    if ship_id in profile.owned_ships:
        return False, "Ya es tuya"
    if galaxies_unlocked(profile) < int(ship["requires_galaxies"]):
        return False, f"Requiere llegar a la galaxia {ship['requires_galaxies']}"
    if profile.credits < int(ship["cost"]):
        return False, f"Faltan {int(ship['cost']) - profile.credits} créditos"
    return True, "Disponible"


def buy_ship(profile: PlayerProfile, ship_id: str, config: GameConfig) -> tuple[bool, str]:
    ok, reason = can_buy_ship(profile, ship_id, config)
    if not ok:
        return False, reason
    profile.credits -= int(config.ships[ship_id]["cost"])
    profile.owned_ships.append(ship_id)
    profile.ship = ship_id
    return True, f"{config.ships[ship_id]['name']} adquirida"


def select_ship(profile: PlayerProfile, ship_id: str) -> bool:
    if ship_id in profile.owned_ships:
        profile.ship = ship_id
        return True
    return False
