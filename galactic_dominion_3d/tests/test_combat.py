import random

from game.combat.damage import DamageInfo, Durability, roll_damage
from game.weapons.weapon import WeaponDef, WeaponState


def test_shield_absorbs_before_hull():
    d = Durability(100, 50)
    r = d.apply(DamageInfo(30))
    assert d.shield == 20 and d.hull == 100 and r.shield_damage == 30


def test_overflow_passes_to_hull_with_multipliers():
    d = Durability(100, 20)
    r = d.apply(DamageInfo(40, shield_mult=2.0, hull_mult=1.5))
    # 20 de escudo absorben 10 de daño bruto (x2); quedan 30 brutos x1.5 = 45 al casco
    assert r.shield_broken
    assert d.shield == 0
    assert abs(d.hull - 55) < 1e-6


def test_destroyed_and_no_damage_after():
    d = Durability(10)
    assert d.apply(DamageInfo(15)).destroyed
    assert d.apply(DamageInfo(5)).hull_damage == 0


def test_shield_regenerates_only_after_delay():
    d = Durability(100, 50, shield_regen=10, shield_delay=2)
    d.apply(DamageInfo(20))
    d.update(1.0)
    assert d.shield == 30
    d.update(1.5)  # supera el retardo
    assert d.shield > 30


def test_crit_roll():
    amount, crit = roll_damage(10, 1.5, 1.0, 2.0, random.Random(0))
    assert crit and amount == 30
    amount, crit = roll_damage(10, 1.0, 0.0, 2.0, random.Random(0))
    assert not crit and amount == 10


def test_weapon_cadence_energy_and_ammo(config):
    cannon = WeaponState(WeaponDef.from_config("energy_cannon", config.weapons["energy_cannon"]))
    assert cannon.can_fire(100)
    cannon.fire()
    assert not cannon.can_fire(100)
    cannon.update(cannon.d.interval)
    assert cannon.can_fire(100)
    assert not cannon.can_fire(0.5)  # sin energía suficiente
    missiles = WeaponState(WeaponDef.from_config("guided_missiles", config.weapons["guided_missiles"]), ammo=1)
    missiles.fire()
    missiles.update(10)
    assert missiles.ammo == 0 and not missiles.can_fire(100)


def test_special_weapon_uses_cooldown(config):
    pulse = WeaponDef.from_config("area_pulse", config.weapons["area_pulse"])
    assert pulse.interval == config.weapons["area_pulse"]["cooldown"]
