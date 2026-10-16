from game.progression.evolution import evolution, tier_changes, tier_for_level
from game.ships.stats import compute_ship_stats


def test_tiers_follow_pilot_level(config):
    assert tier_for_level(1, config) == 1
    assert tier_for_level(3, config) == 1
    assert tier_for_level(4, config) == 2
    assert tier_for_level(8, config) == 3
    assert tier_for_level(50, config) == 5


def test_higher_tiers_hit_harder_and_sound_heavier(config):
    mk1, mk3, mk5 = evolution(1, config), evolution(8, config), evolution(16, config)
    assert mk1.extra_projectiles == 0 and mk3.extra_projectiles == 1 and mk5.extra_projectiles == 2
    # ráfaga doble: 2 x 65% = 130% del daño por disparo
    assert 2 * mk3.shot_damage > 1.0
    assert mk1.bolt_size < mk3.bolt_size < mk5.bolt_size
    assert mk1.sound_rate > mk3.sound_rate > mk5.sound_rate
    assert mk5.next_level is None and mk1.next_level == 4


def test_tier_raises_real_hull_shield_and_damage(profile, config):
    profile.level = 3
    before = compute_ship_stats(profile, config)
    profile.level = 4  # pasa de Mk I a Mk II
    after = compute_ship_stats(profile, config)
    assert after.tier == 2 and before.tier == 1
    base_hull = config.ships[profile.ship]["hull"]
    assert abs((after.max_hull - before.max_hull) - base_hull * (0.1 + 0.015)) < 1e-6
    assert after.damage_mult > before.damage_mult + 0.07 - 1e-9


def test_tier_changes_reports_every_new_stage(config):
    reached = tier_changes(3, 12, config)
    assert [e.name for e in reached] == ["Mk II", "Mk III", "Mk IV"]
    assert tier_changes(5, 6, config) == []
