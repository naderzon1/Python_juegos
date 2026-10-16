import random

from game.inventory.items import equip_component, generate_component, roll_rarity
from game.progression.leveling import add_xp, xp_for_next_level
from game.ships.stats import compute_ship_stats


def test_xp_curve_grows(config):
    assert xp_for_next_level(1, config) < xp_for_next_level(2, config) < xp_for_next_level(10, config)


def test_add_xp_levels_up_and_keeps_remainder(profile, config):
    needed = xp_for_next_level(1, config)
    levels = add_xp(profile, needed + 5, config)
    assert levels == [2]
    assert profile.level == 2
    assert profile.xp == 5


def test_add_xp_multiple_levels(profile, config):
    total = sum(xp_for_next_level(level, config) for level in range(1, 4))
    assert add_xp(profile, total, config) == [2, 3, 4]


def test_upgrades_change_real_stats(profile, config):
    base = compute_ship_stats(profile, config)
    profile.upgrades["shields"] = 3
    profile.upgrades["firepower"] = 2
    profile.upgrades["missiles"] = 1
    upgraded = compute_ship_stats(profile, config)
    assert upgraded.max_shield > base.max_shield
    assert abs(upgraded.max_shield - base.max_shield * 1.36) < 1e-6
    assert abs(upgraded.damage_mult - (base.damage_mult + 0.16)) < 1e-6
    assert upgraded.missile_capacity == base.missile_capacity + 2


def test_pilot_level_and_components_add_bonuses(profile, config):
    base = compute_ship_stats(profile, config)
    profile.level = 5
    item = generate_component(random.Random(1), config, tier=1, rarity="epic")
    item["stat"], item["value"] = "max_hull", 0.2
    profile.inventory.append(item)
    ok, _ = equip_component(profile, item["id"], base.component_slots)
    assert ok
    stats = compute_ship_stats(profile, config)
    expected = base.max_hull * (1 + 0.015 * 4 + 0.1 + 0.2)  # nivel 5 = etapa Mk II (+10% casco)
    assert abs(stats.max_hull - expected) < 1e-6


def test_component_slots_are_limited(profile, config):
    rng = random.Random(2)
    items = [generate_component(rng, config) for _ in range(3)]
    profile.inventory.extend(items)
    assert equip_component(profile, items[0]["id"], 2)[0]
    assert equip_component(profile, items[1]["id"], 2)[0]
    assert not equip_component(profile, items[2]["id"], 2)[0]


def test_higher_tier_improves_rarity_odds(config):
    rng = random.Random(3)
    low = sum(roll_rarity(rng, config, tier=1) in ("epic", "legendary") for _ in range(4000))
    high = sum(roll_rarity(rng, config, tier=5) in ("epic", "legendary") for _ in range(4000))
    assert high > low
