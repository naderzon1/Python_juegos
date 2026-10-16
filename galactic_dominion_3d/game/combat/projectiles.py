"""Proyectiles, misiles guiados, torpedos y rayos láser.

Las colisiones se calculan con el segmento recorrido en cada fotograma
contra las esferas de colisión de los objetivos, así los disparos rápidos no
atraviesan naves aunque el fotograma sea largo. Los nodos visuales se
reutilizan desde una reserva para no crear y destruir geometría en cada tiro.
"""
from __future__ import annotations

import math

from panda3d.core import ColorBlendAttrib, NodePath, Point3, Quat, Vec3

from game.combat.world import segment_sphere
from game.graphics.effects import engine_sprite
from game.graphics.procedural import MeshBuilder
from game.graphics.textures import glow_texture

PURE_ADD = ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne)


class Projectile:
    __slots__ = ("kind", "pos", "vel", "speed", "faction", "wdef", "source", "mult", "crit_bonus", "life",
                 "target", "node", "trail_t", "radius", "boost")


def _bolt_template(glow) -> NodePath:
    b = MeshBuilder()
    b.box((0, 0, 0), (0.22, 1.0, 0.22), (1, 1, 1, 1))
    root = NodePath("bolt")
    core = b.build("bolt-core")
    core.reparentTo(root)
    core.setLightOff(1)
    card = engine_sprite(root, (0, 0, 0), 1.0, (1, 1, 1), glow)
    card.setName("bolt-glow")
    return root


def _missile_template(glow) -> NodePath:
    b = MeshBuilder(0.5, 0.0)
    b.cylinder((0, -1.0, 0), (0, 0.9, 0), 0.22, 0.22, 8, (0.75, 0.77, 0.8, 1))
    b.cylinder((0, 0.9, 0), (0, 1.4, 0), 0.22, 0.02, 8, (0.8, 0.3, 0.2, 1))
    for ang in (0, 90, 180, 270):
        r = math.radians(ang)
        tip = (math.cos(r) * 0.6, -1.0, math.sin(r) * 0.6)
        b.plate([(0, -0.4, 0), tip, (tip[0], -1.1, tip[2]), (0, -1.0, 0)],
                (-math.sin(r), 0, math.cos(r)), 0.05, (0.4, 0.42, 0.45, 1))
    root = NodePath("missile")
    body = b.build("missile-body")
    body.reparentTo(root)
    engine_sprite(root, (0, -1.2, 0), 0.6, (1.0, 0.7, 0.3), glow).setName("missile-glow")
    return root


class ProjectileSystem:
    def __init__(self, world, effects, audio):
        self.world = world
        self.effects = effects
        self.audio = audio
        self.root = world.render.attachNewNode("projectiles")
        self.root.setFogOff(1)
        glow = glow_texture(64, 2.2)
        self.templates = {"bolt": _bolt_template(glow), "missile": _missile_template(glow),
                          "torpedo": _bolt_template(glow)}
        self.free: dict[str, list] = {k: [] for k in self.templates}
        self.active: list[Projectile] = []
        self.beams: list = []
        b = MeshBuilder()
        b.box((0, 0.5, 0), (1, 1, 1), (1, 1, 1, 1))
        self.beam_template = b.build("beam")
        self.beam_template.setLightOff(1)
        self.beam_template.setAttrib(PURE_ADD)
        self.beam_template.setDepthWrite(False)
        self.beam_template.setBin("fixed", 25)
        self.rocks: list = []

    # --- reserva ------------------------------------------------------------
    def _acquire(self, kind: str) -> NodePath:
        pool = self.free[kind]
        if pool:
            node = pool.pop()
            node.show()
            return node
        return self.templates[kind].copyTo(self.root)

    def _release(self, p: Projectile) -> None:
        p.node.hide()
        self.free[p.kind].append(p.node)

    # --- disparos -----------------------------------------------------------
    def fire(self, kind: str, source, origin: Point3, direction: Vec3, wdef, faction: str, mult: float = 1.0,
             crit_bonus: float = 0.0, target=None, inherit: Vec3 | None = None, speed_mult: float = 1.0,
             size_mult: float = 1.0) -> Projectile:
        p = Projectile()
        p.kind = kind
        p.pos = Point3(origin)
        d = Vec3(direction)
        d.normalize()
        p.speed = wdef.projectile_speed * speed_mult
        p.vel = d * p.speed + (inherit if inherit is not None and kind == "bolt" else Vec3(0, 0, 0))
        p.faction, p.wdef, p.source = faction, wdef, source
        p.mult, p.crit_bonus = mult, crit_bonus
        p.life = wdef.lifetime if kind != "bolt" else wdef.range / max(1.0, wdef.projectile_speed)
        p.target = target
        p.trail_t = 0.0
        p.radius = 0.6 * wdef.size * size_mult
        p.boost = 0.0
        p.node = self._acquire(kind)
        c = wdef.color
        if kind == "missile":
            p.node.setScale(size_mult)
            p.node.find("missile-glow").setColorScale(c[0] * 2.2, c[1] * 2.2, c[2] * 2.2, 1)
        else:
            length = ((3.5 + wdef.size * 2.5) if kind == "bolt" else 4.0) * size_mult
            width = (1.0 + wdef.size * (0.9 if kind == "bolt" else 2.5)) * size_mult
            p.node.find("bolt-core").setScale(width, length, width)
            p.node.find("bolt-glow").setScale(width * (1.6 if kind == "bolt" else 2.4))
            k = (3.2 if kind == "bolt" else 4.5) * (0.85 + 0.15 * size_mult)
            p.node.setColorScale(c[0] * k, c[1] * k, c[2] * k, 1)
        p.node.setPos(p.pos)
        p.node.lookAt(p.pos + p.vel)
        self.active.append(p)
        self.effects.muzzle(origin, c, wdef.size * size_mult)
        return p

    def fire_beam(self, source, origin: Point3, direction: Vec3, wdef, faction: str, mult: float = 1.0,
                  crit_bonus: float = 0.0, width: float = 0.6, life: float = 0.09, amount: float | None = None):
        d = Vec3(direction)
        d.normalize()
        hit = self.world.raycast(origin, d, wdef.range, faction)
        length = hit[2] if hit else wdef.range
        if hit and (amount is None or amount > 0):  # amount=0: rayo de aviso sin daño
            self.world.damage(hit[0], wdef, source, hit[1], mult, crit_bonus, amount=amount)
            self.effects.sparks(hit[1], wdef.color, 8)
        node = self.beam_template.copyTo(self.root)
        node.setPos(origin)
        node.lookAt(origin + d)
        node.setScale(width, length, width)
        c = wdef.color
        node.setColorScale(c[0] * 4, c[1] * 4, c[2] * 4, 1)
        self.beams.append([node, life, life, width])
        self.effects.muzzle(origin, c, 1.4)
        return hit

    # --- actualización ------------------------------------------------------
    def update(self, dt: float) -> None:
        keep = []
        for p in self.active:
            if not self._step(p, dt):
                self._release(p)
            else:
                keep.append(p)
        self.active = keep
        beams = []
        for beam in self.beams:
            node, life, total, width = beam
            beam[1] = life - dt
            if beam[1] <= 0:
                node.removeNode()
                continue
            k = beam[1] / total
            node.setSx(width * (0.3 + 0.7 * k))
            node.setSz(width * (0.3 + 0.7 * k))
            beams.append(beam)
        self.beams = beams

    def _step(self, p: Projectile, dt: float) -> bool:
        p.life -= dt
        if p.kind in ("missile", "torpedo"):
            if p.target is not None and (not p.target.alive or getattr(p.target, "evading", False)):
                if getattr(p.target, "evading", False):
                    self.audio.play("evade", 0.3, p.pos)
                p.target = None
            if p.target is not None:
                t_lead = (p.target.pos - p.pos).length() / max(p.speed, 1.0)
                desired = p.target.pos + p.target.velocity * t_lead * 0.6 - p.pos
                self._turn(p, desired, p.wdef.turn_rate * dt)
            p.trail_t -= dt
            if p.trail_t <= 0:
                p.trail_t = 0.025
                self.effects.trail(p.pos, (1.0, 0.6, 0.3) if p.kind == "missile" else p.wdef.color,
                                   1.6 if p.kind == "missile" else 4.0, 0.4 if p.kind == "missile" else 0.6)
        new_pos = p.pos + p.vel * dt
        hit = self._collide(p, p.pos, new_pos)
        if hit:
            self._impact(p, hit[0], hit[1])
            return False
        for center, radius in self.rocks:
            if segment_sphere(p.pos, new_pos, center, radius) is not None:
                self.effects.sparks(new_pos, p.wdef.color, 4)
                if p.wdef.explosion_radius > 0:
                    self._explode(p, new_pos, None)
                return False
        p.pos = new_pos
        p.node.setPos(p.pos)
        if p.kind != "bolt":
            p.node.lookAt(p.pos + p.vel)
        if p.life <= 0:
            if p.kind in ("missile", "torpedo") or p.wdef.explosion_radius > 0:
                self._explode(p, p.pos, None)
            return False
        return True

    def _turn(self, p: Projectile, desired: Vec3, max_deg: float) -> None:
        if desired.length() < 1e-3:
            return
        desired.normalize()
        cur = Vec3(p.vel)
        cur.normalize()
        dot = max(-1.0, min(1.0, cur.dot(desired)))
        angle = math.degrees(math.acos(dot))
        if angle < 1e-3:
            return
        axis = cur.cross(desired)
        if axis.length() < 1e-6:
            return
        axis.normalize()
        q = Quat()
        q.setFromAxisAngle(min(angle, max_deg), axis)
        p.vel = q.xform(cur) * p.speed

    def _collide(self, p: Projectile, p0: Point3, p1: Point3):
        seg = (p1 - p0).length()
        best = None
        for target in self.world.hostiles_of(p.faction):
            center = target.pos
            if (center - p1).length() > target.bound_radius + seg + p.radius:
                continue
            for c, r in target.world_spheres():
                t = segment_sphere(p0, p1, c, r + p.radius)
                if t is None:
                    continue
                # los puntos débiles están sobre el casco del jefe: si el disparo los toca, cuentan primero
                priority = 0 if target.kind == "weak_point" else 1
                if best is None or (priority, t) < (best[3], best[2]):
                    best = (target, p0 + (p1 - p0) * t, t, priority)
        return best

    def _impact(self, p: Projectile, target, point: Point3) -> None:
        if p.wdef.explosion_radius > 0:
            self.world.damage(target, p.wdef, p.source, point, p.mult, p.crit_bonus)
            self._explode(p, point, target)
        else:
            self.world.damage(target, p.wdef, p.source, point, p.mult, p.crit_bonus)

    def _explode(self, p: Projectile, point: Point3, direct_target) -> None:
        radius = p.wdef.explosion_radius
        if radius > 0:
            for target in self.world.hostiles_of(p.faction):
                if target is direct_target:
                    continue
                dist = (target.pos - point).length() - target.bound_radius * 0.5
                if dist < radius:
                    falloff = 1.0 - max(0.0, dist) / radius * 0.6
                    self.world.damage(target, p.wdef, p.source, None, p.mult * falloff * 0.6, p.crit_bonus)
        size = max(0.6, radius / 14.0)
        self.effects.explosion(point, size, p.wdef.color, debris=False)
        self.audio.play("explosion_small", min(1.0, 0.5 + size * 0.15), point)

    def incoming_missiles(self, entity) -> list:
        return [p for p in self.active if p.kind in ("missile", "torpedo") and p.target is entity]

    def count(self) -> int:
        return len(self.active) + len(self.beams)

    def destroy(self) -> None:
        self.root.removeNode()
        self.active.clear()
        self.beams.clear()
