"""Modelos 3D procedurales: naves, jefes, estaciones, carguero, portal y rocas.

Cada nave se compone de un casco iluminado (con material especular y la
textura de paneles) y una capa emisiva (motores, franjas, ventanas) que no
recibe luz y se ve más brillante que 1.0, de modo que el bloom la resalta.

``build_ship`` devuelve un ``ShipModel`` con los puntos útiles para el juego:
toberas de motor, bocas de cañón, puntos débiles y esferas de colisión.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from panda3d.core import Material, NodePath, Point3, TransparencyAttrib, Vec3

from game.graphics.procedural import MeshBuilder, section
from game.graphics.textures import panel_texture

_PANELS = None


def panels():
    global _PANELS
    if _PANELS is None:
        _PANELS = panel_texture(11)
    return _PANELS


def hull_material(shininess: float = 48.0, spec: float = 0.85) -> Material:
    mat = Material("hull")
    mat.setSpecular((spec, spec, spec * 1.05, 1))
    mat.setShininess(shininess)
    return mat


def _scale(c, k):
    return (c[0] * k, c[1] * k, c[2] * k, 1.0)


DARK = (0.16, 0.17, 0.2, 1.0)


@dataclass
class ShipModel:
    root: NodePath
    hull: NodePath
    glow: NodePath
    engines: list = field(default_factory=list)       # (punto local, radio)
    muzzles: list = field(default_factory=list)       # puntos locales
    weak_points: list = field(default_factory=list)   # (punto local, radio)
    hit_spheres: list = field(default_factory=list)   # (punto local, radio)
    length: float = 10.0
    glow_color: tuple = (1, 1, 1)


def finish(name: str, hull: MeshBuilder, glow: MeshBuilder, glass: MeshBuilder | None = None,
           scale: float = 1.0, glow_boost: float = 2.6) -> tuple[NodePath, NodePath, NodePath]:
    root = NodePath(name)
    hull_np = hull.build(name + "-hull")
    hull_np.reparentTo(root)
    hull_np.setTexture(panels())
    hull_np.setMaterial(hull_material())
    if glass and glass.verts:
        glass_np = glass.build(name + "-glass")
        glass_np.reparentTo(hull_np)
        glass_np.setMaterial(hull_material(110, 1.0), 1)
        glass_np.setTextureOff(1)
    glow_np = glow.build(name + "-glow")
    glow_np.reparentTo(root)
    glow_np.setLightOff(1)
    glow_np.setTextureOff(1)
    glow_np.setColorScale(glow_boost, glow_boost, glow_boost, 1)
    root.setScale(scale)
    return root, hull_np, glow_np


# =============================================================================
# Naves del jugador
# =============================================================================
def _player_vanguard(cfg, seed, long=1.0, wide=1.0, engines=2, swept=1.0):
    P, S = tuple(cfg["primary"]) + (1,), tuple(cfg["secondary"]) + (1,)
    G = tuple(cfg["glow"]) + (1,)
    hull, glow, glass = MeshBuilder(0.35, 0.05, seed), MeshBuilder(), MeshBuilder()
    lp = long

    def fus_color(i, j):
        if j in (1, 2):
            return P
        if j in (0, 3):
            return S if 1 <= i <= 3 else P
        return _scale(P, 0.62)

    hull.loft([section(-3.6 * lp, .75 * wide, .5), section(-3.0 * lp, 1.0 * wide, .68),
               section(-1.0 * lp, 1.15 * wide, .78), section(1.5 * lp, .95 * wide, .66),
               section(3.6 * lp, .5 * wide, .38, z=-.05), section(5.7 * lp, .08, .06, z=-.12)], fus_color)
    glass.loft([section(2.9 * lp, .06, .05, .42, 6), section(2.2 * lp, .34, .28, .5, 6), section(0.9 * lp, .4, .32, .58, 6),
                section(-0.4 * lp, .3, .22, .55, 6), section(-1.1 * lp, .06, .05, .5, 6)], (0.05, 0.12, 0.2, 1))
    for side in (-1, 1):
        sx = side
        tip_y = -1.4 * swept
        wing = [(.9 * sx * wide, 1.4, -.15), (4.4 * sx * wide, tip_y, -.15), (4.6 * sx * wide, tip_y - 1.1, -.15),
                (1.0 * sx * wide, -2.6, -.15)]
        hull.plate(wing, (0, 0, 1), .2, P, edge_color=DARK)
        glow.plate([(1.25 * sx * wide, 1.0, -.03), (4.3 * sx * wide, tip_y + .05, -.03),
                    (4.3 * sx * wide, tip_y - .2, -.03), (1.25 * sx * wide, .7, -.03)], (0, 0, 1), .04, G)
        gx = 4.55 * sx * wide
        hull.cylinder((gx, tip_y - 0.9, -.15), (gx, tip_y + 2.3, -.15), .13, .1, 6, DARK)
        hull.plate([(.86 * sx * wide, -1.8 * lp, .5), (1.05 * sx * wide, -3.4 * lp, 1.9),
                    (1.1 * sx * wide, -3.85 * lp, 1.9), (.92 * sx * wide, -3.6 * lp, .5)], (1, 0, 0), .12, S)
        hull.box((1.05 * sx * wide, .2, -.28), (.36, 1.7, .42), DARK)
        nav = (0.1, 1.0, 0.25, 1) if side > 0 else (1.0, 0.12, 0.12, 1)
        glow.box((4.62 * sx * wide, tip_y - 1.15, -.15), (.14, .14, .14), nav)
    engine_pts = []
    xs = [0.0] if engines == 1 else ([-.72 * wide, .72 * wide] if engines == 2 else [-1.0 * wide, 0, 1.0 * wide])
    for ex in xs:
        r = .62 if engines == 1 else .45
        hull.cylinder((ex, -2.3 * lp, -.05), (ex, -4.0 * lp, -.05), r * .92, r * 1.1, 10, DARK)
        glow.cylinder((ex, -3.98 * lp, -.05), (ex, -4.05 * lp, -.05), r * .85, r * .85, 10, G)
        engine_pts.append((Point3(ex, -4.15 * lp, -.05), r))
    muzzles = [Point3(4.55 * wide, 0.9, -.15), Point3(-4.55 * wide, 0.9, -.15)]
    return hull, glow, glass, engine_pts, muzzles


GOLD_TRIM = (0.95, 0.72, 0.25, 1)


def _evolution_parts(hull, glow, cfg, tier: int, wide: float, lp: float, swept: float, muzzles, engines) -> None:
    """Piezas que la nave gana al evolucionar (Mk II-V). Cada etapa se suma a la anterior."""
    P, S = tuple(cfg["primary"]) + (1,), tuple(cfg["secondary"]) + (1,)
    G = tuple(cfg["glow"]) + (1,)
    trim = GOLD_TRIM if tier >= 5 else S
    tip_y = -1.4 * swept
    if tier >= 2:  # placas de blindaje laterales y franja de energía dorsal
        for side in (-1, 1):
            hull.box((side * 1.12 * wide, -1.3 * lp, .25), (.22, 2.6 * lp, .55), _scale(P, .85))
            hull.box((side * 1.0 * wide, 1.0 * lp, .2), (.18, 1.4 * lp, .4), trim)
        glow.box((0, -1.0 * lp, .79), (.08, 3.2 * lp, .05), G)
    if tier >= 3:  # cañones gemelos bajo las alas y aletas ampliadas
        for side in (-1, 1):
            gx = 2.5 * side * wide
            hull.cylinder((gx, -1.6, -.32), (gx, 1.6, -.32), .16, .12, 8, DARK)
            hull.box((gx, -0.6, -.24), (.3, 1.2, .2), trim)
            glow.cylinder((gx, 1.6, -.32), (gx, 1.68, -.32), .09, .09, 8, G)
            muzzles.append(Point3(gx, 1.7, -.32))
            hull.plate([(.95 * side * wide, -2.6 * lp, 1.85), (1.15 * side * wide, -3.7 * lp, 2.6),
                        (1.2 * side * wide, -4.0 * lp, 2.6), (1.08 * side * wide, -3.85 * lp, 1.85)], (1, 0, 0), .1,
                       trim)
            glow.box((1.2 * side * wide, -3.9 * lp, 2.6), (.1, .3, .08), G)
    if tier >= 4:  # alerones delanteros, alas extendidas y toberas auxiliares
        for side in (-1, 1):
            hull.plate([(.45 * side * wide, 3.0 * lp, -.05), (1.7 * side * wide, 2.2 * lp, -.05),
                        (1.75 * side * wide, 1.9 * lp, -.05), (.5 * side * wide, 2.2 * lp, -.05)], (0, 0, 1), .1, S)
            hull.plate([(4.4 * side * wide, tip_y, -.15), (5.6 * side * wide, tip_y - 1.6, -.15),
                        (5.6 * side * wide, tip_y - 2.0, -.15), (4.6 * side * wide, tip_y - 1.1, -.15)], (0, 0, 1),
                       .14, P, edge_color=trim)
            glow.box((5.55 * side * wide, tip_y - 1.8, -.15), (.12, .4, .1), G)
            ex = 1.55 * side * wide
            hull.cylinder((ex, -2.4 * lp, -.3), (ex, -3.6 * lp, -.3), .26, .3, 8, DARK)
            glow.cylinder((ex, -3.58 * lp, -.3), (ex, -3.64 * lp, -.3), .24, .24, 8, G)
            engines.append((Point3(ex, -3.72 * lp, -.3), .28))
    if tier >= 5:  # remates dorados y cresta dorsal de élite
        for side in (-1, 1):
            hull.plate([(.95 * side * wide, 1.45, -.02), (4.4 * side * wide, tip_y + .1, -.02),
                        (4.4 * side * wide, tip_y - .1, -.02), (.95 * side * wide, 1.2, -.02)], (0, 0, 1), .06,
                       GOLD_TRIM)
        hull.plate([(0, 1.8 * lp, .7), (0, -1.5 * lp, 1.25), (0, -2.6 * lp, 1.25), (0, -2.4 * lp, .7)], (1, 0, 0),
                   .1, GOLD_TRIM)
        glow.box((0, -2.0 * lp, 1.27), (.06, 1.0, .05), G)


def build_player_ship(model_cfg: dict, seed: int = 1, tier: int = 1) -> ShipModel:
    """Nave del jugador; ``tier`` (1-5) es la etapa de evolución Mk I-V."""
    kind = model_cfg.get("hull", "player_vanguard")
    if kind == "player_raptor":
        hull, glow, glass, engines, muzzles = _player_vanguard(model_cfg, seed, long=1.18, wide=.85, engines=1,
                                                               swept=-0.4)
    elif kind == "player_bastion":
        hull, glow, glass, engines, muzzles = _player_vanguard(model_cfg, seed, long=1.05, wide=1.35, engines=3,
                                                               swept=0.6)
        P = tuple(model_cfg["primary"]) + (1,)
        for side in (-1, 1):
            hull.box((side * 2.2, -0.8, .25), (1.2, 2.6, .5), _scale(P, 0.8))
            hull.box((side * 1.4, 1.6, -.1), (.6, 1.8, .6), DARK)
    else:
        hull, glow, glass, engines, muzzles = _player_vanguard(model_cfg, seed)
    shape = {"player_raptor": (.85, 1.18, -0.4), "player_bastion": (1.35, 1.05, 0.6)}.get(kind, (1.0, 1.0, 1.0))
    _evolution_parts(hull, glow, model_cfg, tier, shape[0], shape[1], shape[2], muzzles, engines)
    root, h, g = finish("player-ship", hull, glow, glass, glow_boost=2.6 + 0.2 * (tier - 1))
    return ShipModel(root, h, g, engines, muzzles, hit_spheres=[(Point3(0, 0, 0), 4.5)], length=10,
                     glow_color=tuple(model_cfg["glow"]))


# =============================================================================
# Naves enemigas
# =============================================================================
def _enemy_parts(cfg: dict, seed: int):
    P, S = tuple(cfg["primary"]) + (1,), tuple(cfg["secondary"]) + (1,)
    G = tuple(cfg["glow"]) + (1,)
    return P, S, G, MeshBuilder(0.3, 0.06, seed), MeshBuilder(), MeshBuilder()


def _dart(cfg, seed):
    P, S, G, hull, glow, glass = _enemy_parts(cfg, seed)
    hull.loft([section(-2.6, .42, .38, sides=6), section(-1.6, .6, .5, sides=6), section(1.0, .48, .38, sides=6),
               section(3.4, .05, .05, sides=6)], lambda i, j: S if j in (1,) else P)
    glass.loft([section(1.6, .05, .05, .34, 5), section(.6, .26, .2, .38, 5), section(-.4, .05, .05, .3, 5)],
               (.25, .05, .03, 1))
    for s in (-1, 1):
        hull.plate([(.4 * s, .3, 0), (2.6 * s, -1.9, 0), (2.6 * s, -2.4, 0), (.4 * s, -1.6, 0)], (0, 0, 1), .14, P,
                   edge_color=S)
        glow.box((2.6 * s, -2.15, 0), (.12, .4, .1), G)
    hull.plate([(0, -.6, .4), (0, -2.5, 1.6), (0, -2.8, 1.6), (0, -2.6, .4)], (1, 0, 0), .1, S)
    hull.cylinder((0, -2.0, 0), (0, -3.1, 0), .32, .38, 8, DARK)
    glow.cylinder((0, -3.08, 0), (0, -3.14, 0), .3, .3, 8, G)
    return hull, glow, glass, [(Point3(0, -3.2, 0), .4)], [Point3(0, 3.2, 0)], 6.5


def _wedge(cfg, seed):
    P, S, G, hull, glow, glass = _enemy_parts(cfg, seed)
    hull.plate([(0, 4.2, 0), (3.4, -2.4, 0), (-3.4, -2.4, 0)], (0, 0, 1), .55, P, edge_color=S)
    hull.loft([section(-2.4, .9, .55, z=.2), section(.5, .75, .5, z=.25), section(2.8, .2, .15, z=.15)], S)
    glass.loft([section(1.8, .05, .05, .55, 6), section(1.0, .3, .2, .62, 6), section(.0, .05, .05, .55, 6)],
               (.3, .08, .04, 1))
    for s in (-1, 1):
        hull.cylinder((1.15 * s, -1.4, -.05), (1.15 * s, -3.0, -.05), .42, .48, 8, DARK)
        glow.cylinder((1.15 * s, -2.98, -.05), (1.15 * s, -3.05, -.05), .38, .38, 8, G)
        hull.plate([(3.0 * s, -1.6, .25), (3.2 * s, -2.4, 1.2), (3.3 * s, -2.6, 1.2), (3.3 * s, -2.4, .25)],
                   (1, 0, 0), .1, S)
        glow.box((1.7 * s, 1.0, .29), (.08, 2.2, .03), G, rot_h=-28 * s)
    engines = [(Point3(1.15 * s, -3.15, -.05), .45) for s in (-1, 1)]
    return hull, glow, glass, engines, [Point3(-1.5, 1.5, 0), Point3(1.5, 1.5, 0)], 8


def _fork(cfg, seed):
    P, S, G, hull, glow, glass = _enemy_parts(cfg, seed)
    for s in (-1, 1):
        x = 1.1 * s
        hull.loft([[p + Vec3(x, 0, 0) for p in section(-2.8, .38, .34, sides=6)],
                   [p + Vec3(x, 0, 0) for p in section(2.6, .32, .28, sides=6)],
                   [p + Vec3(x * .9, 0, 0) for p in section(4.8, .05, .05, sides=6)]],
                  lambda i, j: S if j in (1, 2) else P)
        hull.cylinder((x, -2.4, 0), (x, -3.5, 0), .3, .36, 8, DARK)
        glow.cylinder((x, -3.48, 0), (x, -3.55, 0), .28, .28, 8, G)
        glow.box((x, 1.0, .3), (.06, 2.6, .04), G)
    hull.loft([section(-1.6, .7, .5), section(.6, .65, .48), section(1.8, .2, .2)], P)
    hull.box((0, -1.2, 0), (2.2, .6, .25), S)
    glass.loft([section(1.4, .05, .05, .42, 5), section(.6, .3, .22, .48, 5), section(-.4, .05, .05, .4, 5)],
               (.3, .05, .06, 1))
    engines = [(Point3(1.1 * s, -3.6, 0), .36) for s in (-1, 1)]
    return hull, glow, glass, engines, [Point3(-1.1, 4.8, 0), Point3(1.1, 4.8, 0)], 8.5


def _heavy(cfg, seed):
    P, S, G, hull, glow, glass = _enemy_parts(cfg, seed)
    hull.loft([section(-4.2, 1.6, 1.0, sides=6), section(-2.5, 1.9, 1.2, sides=6), section(2.5, 1.7, 1.1, sides=6),
               section(4.6, .9, .6, sides=6)], lambda i, j: S if i == 1 and j in (1, 2) else P)
    hull.box((0, -1.0, 1.3), (1.8, 3.2, .8), _scale(P, .85))
    hull.box((0, -2.0, 1.95), (1.0, 1.0, .6), S)
    glow.box((0, -1.55, 2.0), (.8, .04, .14), G)
    for s in (-1, 1):
        hull.box((2.1 * s, 0, -.2), (.9, 5.0, 1.0), _scale(P, .7))
        for y in (1.6, -1.2):
            hull.cylinder((1.0 * s, y, 1.1), (1.0 * s, y, 1.5), .45, .4, 8, DARK)
            hull.cylinder((1.0 * s, y, 1.35), (1.0 * s, y + 1.6, 1.35), .09, .09, 6, DARK)
        for z in (.35, -.55):
            hull.cylinder((1.0 * s, -4.0, z), (1.0 * s, -5.0, z), .42, .5, 8, DARK)
            glow.cylinder((1.0 * s, -4.98, z), (1.0 * s, -5.05, z), .38, .38, 8, G)
        glow.box((2.56 * s, 0, -.2), (.04, 3.5, .12), G)
    engines = [(Point3(1.0 * s, -5.15, z), .5) for s in (-1, 1) for z in (.35, -.55)]
    muzzles = [Point3(1.0 * s, y + 1.6, 1.35) for s in (-1, 1) for y in (1.6, -1.2)]
    return hull, glow, glass, engines, muzzles, 10


def _alien(cfg, seed, length=1.0, spikes=7):
    P, S, G, hull, glow, glass = _enemy_parts(cfg, seed)
    rng = random.Random(seed)
    secs = []
    for i, (y, w) in enumerate([(-3.0, .35), (-2.0, .9), (-.6, 1.25), (.8, 1.0), (2.0, .7), (3.2, .15)]):
        sec = section(y * length, w * rng.uniform(.9, 1.15), w * .8 * rng.uniform(.9, 1.15), sides=7)
        secs.append([p + Vec3(rng.uniform(-.08, .08), 0, rng.uniform(-.08, .08)) for p in sec])
    hull.loft(secs, lambda i, j: S if j in (1, 2) and i % 2 else P)
    for k in range(spikes):
        y = (-1.8 + 3.4 * k / max(1, spikes - 1)) * length
        ang = rng.uniform(-0.9, 0.9)
        base = Point3(math.sin(ang) * .7, y, math.cos(ang) * .6)
        tip = base + Vec3(math.sin(ang) * 1.6, -0.9, math.cos(ang) * 1.4)
        hull.cylinder(base, tip, .18, .02, 5, S)
    for k in range(4):
        y = (-1.6 + k * 1.1) * length
        for s in (-1, 1):
            glow.icosphere((s * .95 * (1 - abs(y) / 5), y, .1), .16, 0, G)
    glow.icosphere((0, -3.05 * length, 0), .3, 1, G)
    engines = [(Point3(0, -3.2 * length, 0), .5)]
    return hull, glow, glass, engines, [Point3(0, 3.2 * length, 0)], 7 * length


def _leviathan(cfg, seed):
    P, S, G, hull, glow, glass = _enemy_parts(cfg, seed)
    rng = random.Random(seed)
    secs = []
    for i in range(10):
        y = -22 + i * 5
        w = 3.2 * math.sin(math.pi * (i + 0.6) / 10.6) + 0.6
        secs.append([p + Vec3(0, 0, math.sin(i * .7) * .6) for p in section(y, w, w * .8, sides=9)])
    hull.loft(secs, lambda i, j: S if j in (2, 3) else P)
    for k in range(10):
        y = -16 + k * 3.4
        for s in (-1, 1):
            base = Point3(s * 2.4, y, -.6)
            tip = base + Vec3(s * rng.uniform(4, 7), rng.uniform(-4, -1), rng.uniform(-3, 0))
            hull.cylinder(base, tip, .45, .05, 5, S)
        glow.icosphere((0, y, 3.0 * math.sin(math.pi * (k + 2) / 13) + .4), .35, 0, G)
    for s in (-1, 1):
        glow.icosphere((s * 1.0, 24, .8), .6, 1, G)
    engines = [(Point3(0, -23, 0), 1.5)]
    return hull, glow, glass, engines, [Point3(0, 25, 0), Point3(-2, 18, 0), Point3(2, 18, 0)], 50


def _void(cfg, seed, scale=1.0, shards=4):
    P, S, G, hull, glow, glass = _enemy_parts(cfg, seed)
    hull.icosphere((0, 0, 0), 1.3 * scale, 0, P, stretch=(1, 2.4, .8))
    glow.icosphere((0, 0, 0), .55 * scale, 1, G, stretch=(1, 1.6, 1))
    rng = random.Random(seed)
    for k in range(shards):
        a = 2 * math.pi * k / shards + rng.uniform(-.2, .2)
        c = (math.cos(a) * 2.3 * scale, rng.uniform(-1.5, 1.0) * scale, math.sin(a) * 1.6 * scale)
        hull.icosphere(c, .55 * scale, 0, S if k % 2 else P, stretch=(.5, 2.2, .5), seed=k)
        glow.box(c, (.1 * scale, 1.6 * scale, .1 * scale), G)
    engines = [(Point3(0, -3.2 * scale, 0), .6 * scale)]
    return hull, glow, glass, engines, [Point3(0, 3.0 * scale, 0)], 7 * scale


def _station(cfg, seed, friendly=False):
    P, S, G, hull, glow, glass = _enemy_parts(cfg, seed)
    hull.cylinder((0, 0, -18), (0, 0, 18), 7, 7, 14, P, cap_color=S)
    hull.cylinder((0, 0, 18), (0, 0, 26), 4, 1.5, 10, S)
    hull.cylinder((0, 0, 26), (0, 0, 40), .4, .2, 5, DARK)
    hull.cylinder((0, 0, -18), (0, 0, -24), 5, 3, 10, DARK)
    segs = 16
    for i in range(segs):
        a = 2 * math.pi * i / segs
        c = (math.cos(a) * 30, math.sin(a) * 30, 0)
        hull.box(c, (12.5, 4.2, 3.6), P if i % 2 else _scale(P, .8), rot_h=math.degrees(a) + 90)
        glow.box((math.cos(a) * 32.2, math.sin(a) * 32.2, 0), (6, .2, .6), G, rot_h=math.degrees(a) + 90)
    for i in range(4):
        a = 2 * math.pi * i / 4 + math.pi / 4
        hull.box((math.cos(a) * 17, math.sin(a) * 17, 0), (24, 2, 2), DARK, rot_h=math.degrees(a))
    for z in range(-15, 16, 5):
        for i in range(8):
            a = 2 * math.pi * i / 8
            glow.box((math.cos(a) * 7.05, math.sin(a) * 7.05, z), (.9, .9, .5), G, rot_h=math.degrees(a))
    if friendly:
        for s in (-1, 1):
            hull.box((0, s * 48, 0), (3, 18, 1), DARK)
            hull.plate([(-14, s * 40, 0), (14, s * 40, 0), (14, s * 70, 0), (-14, s * 70, 0)], (0, 0, 1), .5,
                       (0.1, 0.16, 0.35, 1), edge_color=DARK)
    weak = [(Point3(math.cos(a) * 30, math.sin(a) * 30, 3.5), 5) for a in (0, math.pi / 2, math.pi, 3 * math.pi / 2)]
    muzzles = [p for p, _ in weak]
    spheres = [(Point3(0, 0, 0), 20)] + [(Point3(math.cos(a) * 30, math.sin(a) * 30, 0), 9)
                                         for a in [2 * math.pi * k / 8 for k in range(8)]]
    return hull, glow, glass, [], muzzles, 70, weak, spheres


ENEMY_BUILDERS = {"dart": _dart, "wedge": _wedge, "fork": _fork, "heavy": _heavy, "alien": _alien,
                  "leviathan": _leviathan, "void": _void}


def build_enemy_ship(model_cfg: dict, seed: int = 1) -> ShipModel:
    kind = model_cfg["hull"]
    scale = float(model_cfg.get("scale", 1.0))
    if kind == "station":
        hull, glow, glass, engines, muzzles, length, weak, spheres = _station(model_cfg, seed)
        root, h, g = finish("station", hull, glow, glass, scale)
        return ShipModel(root, h, g, engines, muzzles, weak_points=weak, hit_spheres=spheres, length=length,
                         glow_color=tuple(model_cfg["glow"]))
    hull, glow, glass, engines, muzzles, length = ENEMY_BUILDERS[kind](model_cfg, seed)
    root, h, g = finish("enemy-" + kind, hull, glow, glass, scale)
    radius = length * 0.55
    return ShipModel(root, h, g, engines, muzzles, hit_spheres=[(Point3(0, 0, 0), radius)], length=length * scale,
                     glow_color=tuple(model_cfg["glow"]))


# =============================================================================
# Jefes (naves capitales)
# =============================================================================
def build_boss(model_cfg: dict, radius: float, weak_count: int, seed: int = 7) -> ShipModel:
    variant = model_cfg.get("variant", "warden")
    P, S, G = tuple(model_cfg["primary"]) + (1,), tuple(model_cfg["secondary"]) + (1,), tuple(model_cfg["glow"]) + (1,)
    hull, glow, glass = MeshBuilder(0.12, 0.05, seed), MeshBuilder(), MeshBuilder()
    rng = random.Random(seed)
    L = radius * 2.3
    if variant in ("warden", "dreadnought", "matriarch"):
        width = L * (0.16 if variant != "matriarch" else 0.12)
        sides = 6 if variant == "dreadnought" else 8
        hull.loft([section(-L * .5, width * .8, width * .45, sides=sides),
                   section(-L * .38, width, width * .55, sides=sides),
                   section(L * .1, width * .9, width * .5, sides=sides),
                   section(L * .36, width * .55, width * .32, sides=sides),
                   section(L * .52, width * .08, width * .06, sides=sides)],
                  lambda i, j: S if j in (1, 2) and i in (1, 2) else P)
        hull.box((0, -L * .2, width * .65), (width * .5, L * .22, width * .5), _scale(P, .8))
        hull.box((0, -L * .26, width * 1.0), (width * .34, L * .08, width * .35), S)
        glow.box((0, -L * .22, width * 1.02), (width * .3, .3, width * .06), G)
        for k in range(14):
            y = -L * .45 + k * L * .065
            for s in (-1, 1):
                hull.box((s * width * rng.uniform(.6, .85), y, rng.uniform(-.2, .35) * width),
                         (width * .18, L * .04, width * .16), _scale(P, rng.uniform(.6, .9)))
        if variant == "matriarch":
            for s in (-1, 1):
                hull.loft([[p + Vec3(s * width * 1.6, 0, 0) for p in section(-L * .35, width * .35, width * .3)],
                           [p + Vec3(s * width * 1.6, 0, 0) for p in section(L * .3, width * .3, width * .25)],
                           [p + Vec3(s * width * 1.3, 0, 0) for p in section(L * .55, .5, .5)]], S)
                hull.box((s * width * 1.0, 0, 0), (width * 1.2, width * .4, width * .2), P)
        for s in (-1, 1):
            hull.plate([(s * width * .7, -L * .1, 0), (s * width * 2.4, -L * .42, 0),
                        (s * width * 2.4, -L * .5, 0), (s * width * .7, -L * .45, 0)], (0, 0, 1), width * .12, P,
                       edge_color=DARK)
        engine_pts = []
        for ex in (-.5, 0, .5):
            for ez in ((-.15, .2) if variant == "dreadnought" else (0,)):
                p0 = (ex * width, -L * .48, ez * width)
                hull.cylinder(p0, (ex * width, -L * .56, ez * width), width * .22, width * .26, 10, DARK)
                glow.cylinder((ex * width, -L * .559, ez * width), (ex * width, -L * .565, ez * width),
                              width * .2, width * .2, 10, G)
                engine_pts.append((Point3(ex * width, -L * .57, ez * width), width * .25))
        weak = []
        for k in range(weak_count):
            t = (k + 0.5) / weak_count
            y = -L * .38 + t * L * .7
            s = -1 if k % 2 else 1
            weak.append((Point3(s * width * .72, y, width * .55), width * .3))
        spheres = [(Point3(0, -L * .5 + (i + 0.5) * L / 5, 0), width * 1.1) for i in range(5)]
    elif variant == "colossus":
        secs = []
        for i in range(9):
            y = -L * .5 + i * L / 8
            w = L * .2 * math.sin(math.pi * (i + .5) / 9) + 2
            secs.append([p + Vec3(0, 0, math.sin(i * .8) * w * .15) for p in section(y, w, w * .75, sides=9)])
        hull.loft(secs, lambda i, j: S if j in (2, 3) else P)
        for k in range(16):
            y = -L * .4 + k * L * .052
            for s in (-1, 1):
                base = Point3(s * L * .15, y, -L * .03)
                tip = base + Vec3(s * rng.uniform(L * .12, L * .22), -rng.uniform(L * .02, L * .1),
                                  -rng.uniform(0, L * .1))
                hull.cylinder(base, tip, L * .025, L * .004, 5, S)
        engine_pts = [(Point3(0, -L * .52, 0), L * .06)]
        weak = []
        for k in range(weak_count):
            t = (k + 0.5) / weak_count
            weak.append((Point3((-1) ** k * L * .1, -L * .35 + t * L * .7, L * .14), L * .045))
        spheres = [(Point3(0, -L * .5 + (i + 0.5) * L / 5, 0), L * .19) for i in range(5)]
        glow.icosphere((0, L * .5, L * .02), L * .03, 1, G)
    else:  # sovereign
        hull.icosphere((0, 0, 0), L * .18, 1, P, stretch=(1, 1.8, .9), roughness=.15, seed=seed)
        glow.icosphere((0, 0, 0), L * .07, 2, G, stretch=(1, 1.5, 1))
        ring = 18
        for k in range(ring):
            a = 2 * math.pi * k / ring
            c = (math.cos(a) * L * .38, 0, math.sin(a) * L * .38)
            hull.icosphere(c, L * .045, 0, S if k % 2 else P, stretch=(.6, .6, 2.4), seed=k)
            glow.box(c, (L * .008, L * .008, L * .08), G)
        for s in (-1, 1):
            hull.icosphere((0, s * L * .3, 0), L * .06, 0, S, stretch=(.6, 2.8, .6), seed=s + 5)
        engine_pts = [(Point3(0, -L * .48, 0), L * .05)]
        weak = []
        for k in range(weak_count):
            a = 2 * math.pi * (k + .5) / weak_count
            weak.append((Point3(math.cos(a) * L * .38, 0, math.sin(a) * L * .38), L * .06))
        spheres = [(Point3(0, 0, 0), L * .26)] + [(p, r * 1.4) for p, r in weak]
    root, h, g = finish("boss-" + variant, hull, glow, glass, 1.0, glow_boost=3.0)
    muzzles = [p for p, _ in weak] + [Point3(0, L * .5, 0)]
    return ShipModel(root, h, g, engine_pts, muzzles, weak_points=weak, hit_spheres=spheres, length=L,
                     glow_color=tuple(model_cfg["glow"]))


def build_weak_point(radius: float, glow_color: tuple, primary: tuple) -> NodePath:
    """Generador expuesto del jefe: cúpula luminosa sobre una base blindada."""
    hull, glow = MeshBuilder(0.4, 0.05, 3), MeshBuilder()
    hull.cylinder((0, 0, -radius * .6), (0, 0, radius * .1), radius * .9, radius * .75, 10,
                  tuple(primary) + (1,))
    glow.icosphere((0, 0, radius * .25), radius * .55, 1, tuple(glow_color) + (1,))
    root, _, _ = finish("weak-point", hull, glow, None, glow_boost=3.2)
    return root


# =============================================================================
# Estructuras, aliados y decorados
# =============================================================================
def build_station(friendly: bool = True, seed: int = 4) -> ShipModel:
    cfg = {"primary": [0.6, 0.63, 0.68], "secondary": [0.15, 0.4, 0.75], "glow": [0.5, 0.85, 1.0]} if friendly else \
        {"primary": [0.4, 0.42, 0.46], "secondary": [0.7, 0.2, 0.15], "glow": [1.0, 0.3, 0.2]}
    hull, glow, glass, engines, muzzles, length, weak, spheres = _station(cfg, seed, friendly=friendly)
    root, h, g = finish("station", hull, glow, glass, 1.0)
    return ShipModel(root, h, g, engines, muzzles, weak_points=weak, hit_spheres=spheres, length=length,
                     glow_color=tuple(cfg["glow"]))


def build_freighter(seed: int = 9) -> ShipModel:
    P, S, G = (0.62, 0.6, 0.55, 1), (0.85, 0.55, 0.15, 1), (0.6, 0.9, 1.0, 1)
    hull, glow = MeshBuilder(0.25, 0.05, seed), MeshBuilder()
    hull.box((0, 0, 0), (3, 34, 3), P)
    hull.loft([section(16, 3.2, 2.8), section(20, 3.4, 3.0), section(24, 1.6, 1.4)], P)
    hull.box((0, 18, 2.6), (2.4, 4, 1.6), S)
    glow.box((0, 20.05, 2.6), (2.0, .1, .5), G)
    rng = random.Random(seed)
    for k in range(6):
        for s in (-1, 1):
            hull.box((s * 3.4, -12 + k * 5, 0), (3.6, 4.4, 3.6), S if rng.random() < .5 else _scale(P, .8))
    for s in (-1, 1):
        hull.cylinder((s * 1.5, -17, 0), (s * 1.5, -21, 0), 1.3, 1.5, 10, DARK)
        glow.cylinder((s * 1.5, -20.98, 0), (s * 1.5, -21.05, 0), 1.2, 1.2, 10, G)
    root, h, g = finish("freighter", hull, glow, None)
    engines = [(Point3(s * 1.5, -21.2, 0), 1.5) for s in (-1, 1)]
    return ShipModel(root, h, g, engines, [], hit_spheres=[(Point3(0, y, 0), 6) for y in (-14, -4, 6, 16)],
                     length=45, glow_color=(0.6, 0.9, 1.0))


def build_asteroid(seed: int, radius: float = 1.0, tone: float = 0.42) -> NodePath:
    rng = random.Random(seed)
    b = MeshBuilder(0.6, 0.12, seed)
    c = (tone * rng.uniform(.85, 1.1), tone * rng.uniform(.8, 1.0), tone * rng.uniform(.75, .95), 1)
    b.icosphere((0, 0, 0), radius, 2, c, roughness=0.35,
                stretch=(rng.uniform(.75, 1.25), rng.uniform(.75, 1.3), rng.uniform(.6, 1.0)), seed=seed)
    np_ = b.build(f"asteroid-{seed}")
    np_.setTexture(panels_rock())
    mat = hull_material(12, 0.15)
    np_.setMaterial(mat)
    return np_


_ROCK = None


def panels_rock():
    global _ROCK
    if _ROCK is None:
        import numpy as np
        from game.graphics.textures import fbm, make_texture
        rng = np.random.default_rng(21)
        n = fbm(256, 256, rng, octaves=6, base=8, aspect=1.0)
        v = 0.65 + n * 0.5
        _ROCK = make_texture(np.dstack([v, v * 0.97, v * 0.93]), "rock", wrap_u=True, wrap_v=True)
    return _ROCK


def build_debris(seed: int) -> NodePath:
    """Restos de nave: placas y vigas retorcidas."""
    rng = random.Random(seed)
    b = MeshBuilder(0.3, 0.15, seed)
    tone = rng.uniform(.25, .45)
    col = (tone, tone, tone * 1.05, 1)
    for _ in range(rng.randint(2, 4)):
        c = (rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(-2, 2))
        b.box(c, (rng.uniform(1, 6), rng.uniform(.3, 4), rng.uniform(.2, 1.2)), col, rot_h=rng.uniform(0, 90))
    b.cylinder((0, 0, 0), (rng.uniform(-6, 6), rng.uniform(-6, 6), rng.uniform(-3, 3)), .35, .3, 6, DARK)
    np_ = b.build(f"debris-{seed}")
    np_.setTexture(panels())
    np_.setMaterial(hull_material(30, .5))
    return np_


def build_salvage_pod(glow_color=(0.4, 1.0, 0.8)) -> NodePath:
    hull, glow = MeshBuilder(0.5, 0.0, 2), MeshBuilder()
    hull.box((0, 0, 0), (2.4, 2.4, 2.4), (0.5, 0.52, 0.55, 1))
    for axis in range(3):
        size = [2.6, 2.6, 2.6]
        size[axis] = 0.25
        glow.box((0, 0, 0), size, tuple(glow_color) + (1,))
    root, _, _ = finish("salvage", hull, glow, None, glow_boost=2.2)
    return root


def build_portal(radius: float = 60.0, color=(0.4, 0.8, 1.0)) -> tuple[NodePath, NodePath]:
    """Anillo del portal de salto. Devuelve (raíz, disco_interior) para aplicar el shader."""
    from game.graphics.procedural import disc
    hull, glow = MeshBuilder(0.1, 0.06, 5), MeshBuilder()
    segs = 24
    for i in range(segs):
        a0, a1 = 2 * math.pi * i / segs, 2 * math.pi * (i + 1) / segs
        p0 = (math.cos(a0) * radius, 0, math.sin(a0) * radius)
        p1 = (math.cos(a1) * radius, 0, math.sin(a1) * radius)
        hull.cylinder(p0, p1, radius * .07, radius * .07, 8, (0.45, 0.47, 0.52, 1))
        if i % 3 == 0:
            hull.box((math.cos(a0) * radius * 1.1, 0, math.sin(a0) * radius * 1.1),
                     (radius * .12, radius * .2, radius * .12), DARK)
            glow.box((math.cos(a0) * radius * 1.17, -radius * .1, math.sin(a0) * radius * 1.17),
                     (radius * .05, radius * .02, radius * .05), tuple(color) + (1,))
    root, _, _ = finish("portal", hull, glow, None)
    inner = disc(radius * 0.95, 64, "portal-disc")
    inner.reparentTo(root)
    inner.setTwoSided(True)
    inner.setLightOff(1)
    inner.setTransparency(TransparencyAttrib.MNone)
    return root, inner
