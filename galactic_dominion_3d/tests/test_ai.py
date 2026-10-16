import random

from panda3d.core import Vec3

from game.ai.fsm import (ATTACK, CHASE, EVADE, FLANK, PATROL, RETREAT, Brain, Perception, SquadCoordinator,
                         angle_between, lead_point)


def perception(**kw):
    base = dict(pos=Vec3(0, 0, 0), forward=Vec3(0, 1, 0), hull_ratio=1.0, target_pos=Vec3(0, 1000, 0),
                target_vel=Vec3(0, 0, 0), target_forward=Vec3(1, 0, 0), projectile_speed=600,
                weapon_range=900, dt=0.1)
    base.update(kw)
    return Perception(**base)


AI = {"preferred_range": 300, "detect_range": 1200, "accuracy": 0.8, "evade_chance": 0.0,
      "retreat_hp": 0.3, "flank": False, "missiles": False}


def test_patrol_detects_target_and_chases():
    brain = Brain(AI, random.Random(1))
    brain.start_patrol(Vec3(0, 0, 0))
    brain.update(perception(target_pos=Vec3(0, 5000, 0)))
    assert brain.state == PATROL
    brain.update(perception(target_pos=Vec3(0, 800, 0)))
    assert brain.state == CHASE


def test_chase_turns_into_attack_and_fires_when_aligned():
    brain = Brain(AI, random.Random(1))
    cmd = brain.update(perception(target_pos=Vec3(0, 400, 0)))
    assert brain.state == ATTACK
    cmd = brain.update(perception(target_pos=Vec3(0, 400, 0)))
    assert cmd.fire
    assert angle_between(cmd.direction, Vec3(0, 1, 0)) < 1


def test_does_not_fire_out_of_range_or_cone():
    brain = Brain(AI, random.Random(1))
    cmd = brain.update(perception(target_pos=Vec3(0, 3000, 0)))
    assert not cmd.fire
    cmd = brain.update(perception(target_pos=Vec3(500, 0, 0)))
    assert not cmd.fire


def test_retreats_when_badly_damaged_only_once():
    brain = Brain(AI, random.Random(1))
    cmd = brain.update(perception(hull_ratio=0.1, target_pos=Vec3(0, 500, 0)))
    assert brain.state == RETREAT
    assert cmd.direction.dot(Vec3(0, 1, 0)) < 0  # se aleja del objetivo
    for _ in range(80):
        brain.update(perception(hull_ratio=0.1, target_pos=Vec3(0, 500, 0)))
    assert brain.state != RETREAT


def test_breaks_off_when_too_close():
    brain = Brain(AI, random.Random(1))
    brain.update(perception(target_pos=Vec3(0, 400, 0)))
    brain.update(perception(target_pos=Vec3(0, 100, 0)))
    assert brain.state == EVADE


def test_without_attack_token_it_flanks():
    brain = Brain(AI, random.Random(1))
    brain.update(perception(target_pos=Vec3(0, 400, 0), may_attack=False))
    assert brain.state == FLANK


def test_squad_limits_simultaneous_attackers():
    class M:
        alive = True
    members = [M() for _ in range(5)]
    squad = SquadCoordinator(max_attackers=2)
    squad.update(0.1, members)
    assert sum(squad.may_attack(m) for m in members) == 2


def test_lead_point_anticipates_motion():
    p = lead_point(Vec3(0, 0, 0), Vec3(0, 600, 0), Vec3(100, 0, 0), 600)
    assert p.x > 0
