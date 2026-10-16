import wave

from panda3d.core import Point3, Vec3

from game.audio import synth
from game.combat.world import CombatWorld, segment_sphere


class FakeTarget:
    def __init__(self, pos, radius, kind="fighter", faction="enemy"):
        self._pos = Point3(*pos)
        self.radius = radius
        self.kind = kind
        self.faction = faction
        self.alive = True
        self.targetable = True
        self.bound_radius = radius

    @property
    def pos(self):
        return self._pos

    def world_spheres(self):
        return [(self._pos, self.radius)]


def make_world(config, *targets):
    world = CombatWorld.__new__(CombatWorld)
    world.entities = list(targets)
    return world


def test_segment_sphere_hits_and_misses():
    assert segment_sphere(Point3(0, -10, 0), Point3(0, 10, 0), Point3(0, 0, 0), 1) is not None
    assert segment_sphere(Point3(5, -10, 0), Point3(5, 10, 0), Point3(0, 0, 0), 1) is None
    # el disparo rápido no atraviesa la nave aunque empiece y acabe fuera de ella
    t = segment_sphere(Point3(0, -50, 0), Point3(0, 50, 0), Point3(0, 0, 0), 2)
    assert 0.4 < t < 0.5


def test_raycast_returns_first_target(config):
    near, far = FakeTarget((0, 100, 0), 5), FakeTarget((0, 300, 0), 5)
    world = make_world(config, far, near)
    hit = world.raycast(Point3(0, 0, 0), Vec3(0, 1, 0), 1000, "player")
    assert hit[0] is near and abs(hit[2] - 95) < 1e-3


def test_raycast_prefers_weak_point_on_boss_surface(config):
    hull = FakeTarget((0, 200, 0), 40, kind="boss")
    weak = FakeTarget((0, 175, 0), 8, kind="weak_point")
    world = make_world(config, hull, weak)
    hit = world.raycast(Point3(0, 0, 0), Vec3(0, 1, 0), 1000, "player")
    assert hit[0] is weak


def test_raycast_ignores_weak_point_hidden_behind_hull(config):
    hull = FakeTarget((0, 200, 0), 40, kind="boss")
    weak = FakeTarget((0, 245, 0), 8, kind="weak_point")
    world = make_world(config, hull, weak)
    hit = world.raycast(Point3(0, 0, 0), Vec3(0, 1, 0), 1000, "player")
    assert hit[0] is hull


def test_raycast_ignores_allies(config):
    ally = FakeTarget((0, 100, 0), 5, faction="player")
    world = make_world(config, ally)
    assert world.raycast(Point3(0, 0, 0), Vec3(0, 1, 0), 1000, "player") is None


def test_synth_writes_valid_wav(tmp_path):
    defs = synth.sfx_defs()
    for name in ("shot_energy", "explosion_small", "ui_click"):
        path = tmp_path / f"{name}.wav"
        synth.write_wav(path, defs[name]())
        with wave.open(str(path)) as handle:
            assert handle.getframerate() == synth.SR
            assert handle.getnframes() > 100
