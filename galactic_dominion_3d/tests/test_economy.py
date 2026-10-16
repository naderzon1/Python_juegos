import random

from game.economy.shop import (buy_ship, buy_upgrade, can_buy_upgrade, can_unlock_weapon, unlock_weapon,
                               upgrade_cost)
from game.inventory.items import generate_component, sell_item, sell_value


def test_upgrade_cost_grows_with_level(config):
    c1, _ = upgrade_cost("firepower", 1, config)
    c5, _ = upgrade_cost("firepower", 5, config)
    assert c5 > c1 * 3


def test_buy_upgrade_spends_credits_and_materials(profile, config):
    profile.credits = 10_000
    profile.materials["alloy"] = 50
    credits, mats = upgrade_cost("hull", 1, config)
    ok, _ = buy_upgrade(profile, "hull", config)
    assert ok
    assert profile.upgrades["hull"] == 1
    assert profile.credits == 10_000 - credits
    assert profile.materials["alloy"] == 50 - mats["alloy"]


def test_cannot_buy_without_funds(profile, config):
    profile.credits = 0
    ok, reason = can_buy_upgrade(profile, "hull", config)
    assert not ok and "créditos" in reason


def test_tech_gate_requires_galaxies(profile, config):
    profile.credits = 10**7
    profile.materials = {m: 10**4 for m in config.economy["materials"]}
    profile.upgrades["speed"] = 3
    ok, reason = can_buy_upgrade(profile, "speed", config)
    assert not ok and "galaxia" in reason
    profile.unlocked_galaxies.append("crimson")
    assert can_buy_upgrade(profile, "speed", config)[0]


def test_weapon_requires_blueprint_then_unlocks(profile, config):
    profile.credits = 5000
    ok, reason = can_unlock_weapon(profile, "precision_laser", config)
    assert not ok and "plano" in reason
    profile.blueprints.append("precision_laser")
    ok, _ = unlock_weapon(profile, "precision_laser", config)
    assert ok
    assert "precision_laser" in profile.unlocked_weapons
    assert profile.credits == 5000 - config.weapons["precision_laser"]["unlock"]["credits"]


def test_buy_ship_requires_progress(profile, config):
    profile.credits = 99999
    assert not buy_ship(profile, "raptor", config)[0]
    profile.unlocked_galaxies.append("crimson")
    assert buy_ship(profile, "raptor", config)[0]
    assert profile.ship == "raptor"


def test_sell_item_gives_credits_and_unequips(profile, config):
    item = generate_component(random.Random(5), config, tier=2, rarity="rare")
    profile.inventory.append(item)
    profile.equipped_components.append(item["id"])
    before = profile.credits
    value = sell_item(profile, item["id"], config)
    assert value == sell_value(item, config) > 0
    assert profile.credits == before + value
    assert item["id"] not in profile.equipped_components
