"""Partículas y efectos (CPU, con reserva de nodos reutilizables).

Hay dos reservas de sprites: aditiva (fuego, chispas, destellos, motores) y
translúcida (humo). Los nodos se crean una vez y se reutilizan, así una
batalla grande no genera basura ni tirones. El tope de partículas sale del
preajuste gráfico; si se alcanza, las partículas nuevas reemplazan a las más
antiguas.
"""
from __future__ import annotations

import random

from panda3d.core import (CardMaker, ColorBlendAttrib, NodePath, Point3, TransparencyAttrib, Vec3, Vec4)

from game.graphics import models
from game.graphics.textures import glow_texture, ring_sprite


class Particle:
    __slots__ = ("np", "pos", "vel", "age", "life", "s0", "s1", "c0", "c1", "drag", "active", "spin", "rot")

    def __init__(self, np_: NodePath):
        self.np = np_
        self.active = False


def _card(name: str) -> NodePath:
    cm = CardMaker(name)
    cm.setFrame(-1, 1, -1, 1)
    return NodePath(cm.generate())


class SpritePool:
    def __init__(self, parent: NodePath, texture, cap: int, additive: bool, name: str):
        self.root = parent.attachNewNode(name)
        self.root.setLightOff(1)
        self.root.setDepthWrite(False)
        self.root.setBin("fixed", 30)
        self.root.setTexture(texture)
        self.root.setFogOff(1)
        if additive:
            self.root.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha,
                                                      ColorBlendAttrib.OOne))
        else:
            self.root.setTransparency(TransparencyAttrib.MAlpha)
        template = _card(name + "-card")
        self.items: list[Particle] = []
        for _ in range(cap):
            np_ = template.copyTo(self.root)
            np_.setBillboardPointEye()
            np_.hide()
            self.items.append(Particle(np_))
        self.free = list(self.items)
        self.active: list[Particle] = []

    def emit(self, pos, vel, life, s0, s1, c0, c1, drag=0.0, spin=0.0) -> None:
        if self.free:
            p = self.free.pop()
        elif self.active:
            p = self.active.pop(0)
        else:
            return
        p.pos, p.vel = Point3(pos), Vec3(vel)
        p.age, p.life = 0.0, max(0.01, life)
        p.s0, p.s1, p.c0, p.c1, p.drag = s0, s1, Vec4(*c0), Vec4(*c1), drag
        p.spin, p.rot = spin, random.uniform(0, 360)
        p.np.show()
        p.np.setPos(p.pos)
        p.active = True
        self.active.append(p)

    def update(self, dt: float) -> None:
        keep = []
        for p in self.active:
            p.age += dt
            if p.age >= p.life:
                p.active = False
                p.np.hide()
                self.free.append(p)
                continue
            t = p.age / p.life
            if p.drag:
                p.vel *= max(0.0, 1.0 - p.drag * dt)
            p.pos += p.vel * dt
            p.np.setPos(p.pos)
            p.np.setScale(p.s0 + (p.s1 - p.s0) * t)
            p.np.setColorScale(p.c0 + (p.c1 - p.c0) * t)
            if p.spin:
                p.rot += p.spin * dt
                p.np.setR(p.rot)
            keep.append(p)
        self.active = keep

    def count(self) -> int:
        return len(self.active)

    def destroy(self) -> None:
        self.root.removeNode()


class Effects:
    def __init__(self, render: NodePath, cap: int, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.root = render.attachNewNode("effects")
        glow = glow_texture(64, 2.0)
        soft = glow_texture(64, 1.3)
        self.add = SpritePool(self.root, glow, cap, True, "fx-add")
        self.smoke = SpritePool(self.root, soft, max(40, cap // 4), False, "fx-smoke")
        self.rings = SpritePool(self.root, ring_sprite(), 16, True, "fx-rings")
        self.debris: list = []
        self.debris_templates = [models.build_debris(i) for i in range(4)]
        self.shake = 0.0  # vibración pendiente para la cámara

    # --- efectos compuestos -------------------------------------------------
    def explosion(self, pos, size: float = 1.0, color=(1.0, 0.6, 0.25), debris: bool = True) -> None:
        r = self.rng
        c = color
        self.add.emit(pos, Vec3(0, 0, 0), 0.25, size * 6, size * 14, (1.6, 1.5, 1.3, 1), (c[0], c[1], c[2], 0))
        for _ in range(int(10 + size * 6)):
            v = Vec3(r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1)) * size * r.uniform(6, 22)
            self.add.emit(pos, v, r.uniform(.4, .9), size * r.uniform(1.5, 3.2), size * r.uniform(4, 7),
                          (c[0] * 1.6, c[1] * 1.4, c[2] * 1.2, 1), (c[0] * .4, c[1] * .15, 0.02, 0), drag=1.5)
        for _ in range(int(8 + size * 6)):
            v = Vec3(r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))
            v.normalize()
            self.add.emit(pos, v * size * r.uniform(30, 80), r.uniform(.3, .8), size * .35, size * .1,
                          (1.6, 1.3, .8, 1), (1, .4, .1, 0), drag=2.0)
        for _ in range(int(3 + size * 2)):
            v = Vec3(r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1)) * size * 5
            self.smoke.emit(pos, v, r.uniform(1.2, 2.4), size * 3, size * 9, (.25, .23, .22, .55), (.1, .1, .1, 0),
                            drag=.8, spin=r.uniform(-30, 30))
        self.rings.emit(pos, Vec3(0, 0, 0), .55, size * 2, size * 22, (c[0] * 1.5, c[1] * 1.5, c[2] * 1.5, .9),
                        (c[0], c[1], c[2], 0))
        if debris and size >= 1.0:
            for _ in range(min(6, int(2 + size * 1.5))):
                self._debris(pos, size)
        self.shake = max(self.shake, min(1.0, size * 0.25))

    def big_explosion(self, pos, size: float, color) -> None:
        for k in range(5):
            offset = Vec3(self.rng.uniform(-1, 1), self.rng.uniform(-1, 1), self.rng.uniform(-1, 1)) * size * 4
            self.explosion(pos + offset, size * self.rng.uniform(.6, 1.1), color, debris=k < 2)
        self.rings.emit(pos, Vec3(0, 0, 0), 1.2, size * 5, size * 70, (1.5, 1.4, 1.2, 1), (color[0], color[1], color[2], 0))
        self.shake = 1.0

    def shockwave(self, pos, radius: float, color) -> None:
        self.rings.emit(pos, Vec3(0, 0, 0), .5, radius * .1, radius * 1.1, (color[0] * 2, color[1] * 2, color[2] * 2, 1),
                        (color[0], color[1], color[2], 0))
        self.add.emit(pos, Vec3(0, 0, 0), .3, radius * .2, radius * .6, (color[0] * 1.5, color[1] * 1.5, color[2] * 1.5, .8),
                      (color[0], color[1], color[2], 0))

    def sparks(self, pos, color=(1, .8, .4), count: int = 6, normal: Vec3 | None = None) -> None:
        r = self.rng
        for _ in range(count):
            v = Vec3(r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))
            if normal is not None:
                v += normal * 1.2
            v.normalize()
            self.add.emit(pos, v * r.uniform(20, 60), r.uniform(.15, .4), .5, .1,
                          (color[0] * 1.6, color[1] * 1.6, color[2] * 1.6, 1), (color[0], color[1] * .5, 0, 0), drag=2.5)
        self.add.emit(pos, Vec3(0, 0, 0), .1, 1.5, 3, (color[0] * 2, color[1] * 2, color[2] * 2, 1), (color[0], color[1], color[2], 0))

    def muzzle(self, pos, color, size: float = 1.0) -> None:
        # destello breve y contenido: con ráfagas múltiples no debe tapar la vista
        size = min(size, 1.6)
        self.add.emit(pos, Vec3(0, 0, 0), .05, size * 0.6, size * 1.1, (color[0] * 1.4, color[1] * 1.4,
                                                                       color[2] * 1.4, 0.8),
                      (color[0], color[1], color[2], 0))

    def trail(self, pos, color, size: float = 1.0, life: float = .35) -> None:
        self.add.emit(pos, Vec3(0, 0, 0), life, size * .9, size * .2, (color[0] * 1.3, color[1] * 1.3, color[2] * 1.3, .8),
                      (color[0] * .5, color[1] * .5, color[2] * .5, 0))

    def smoke_puff(self, pos, size: float = 1.0) -> None:
        r = self.rng
        self.smoke.emit(pos, Vec3(r.uniform(-2, 2), r.uniform(-2, 2), r.uniform(1, 4)), r.uniform(.8, 1.4), size,
                        size * 3.5, (.3, .28, .26, .5), (.12, .12, .12, 0), drag=.5)
        if r.random() < 0.3:
            self.add.emit(pos, Vec3(0, 0, 0), .2, size * .6, size * .2, (1.6, .8, .3, 1), (1, .3, 0, 0))

    def _debris(self, pos, size: float) -> None:
        if len(self.debris) > 30:
            old = self.debris.pop(0)
            old[0].removeNode()
        template = self.rng.choice(self.debris_templates)
        node = template.copyTo(self.root)
        node.setPos(pos)
        node.setScale(self.rng.uniform(.15, .35) * size)
        vel = Vec3(self.rng.uniform(-1, 1), self.rng.uniform(-1, 1), self.rng.uniform(-1, 1)) * self.rng.uniform(10, 35)
        spin = Vec3(self.rng.uniform(-200, 200), self.rng.uniform(-200, 200), self.rng.uniform(-200, 200))
        self.debris.append([node, vel, spin, self.rng.uniform(4, 7)])

    # --- actualización ------------------------------------------------------
    def update(self, dt: float) -> None:
        self.add.update(dt)
        self.smoke.update(dt)
        self.rings.update(dt)
        keep = []
        for item in self.debris:
            node, vel, spin, life = item
            item[3] = life - dt
            if item[3] <= 0:
                node.removeNode()
                continue
            node.setPos(node.getPos() + vel * dt)
            node.setHpr(node.getHpr() + spin * dt)
            if item[3] < 1.0:
                node.setScale(node.getScale() * max(0.0, 1 - dt * 2))
            keep.append(item)
        self.debris = keep

    def count(self) -> int:
        return self.add.count() + self.smoke.count() + self.rings.count() + len(self.debris)

    def destroy(self) -> None:
        self.root.removeNode()
        self.debris.clear()


def engine_sprite(parent: NodePath, pos, radius: float, color, texture) -> NodePath:
    """Resplandor de tobera (billboard aditivo) para naves y misiles."""
    card = _card("engine-glow")
    card.reparentTo(parent)
    card.setPos(pos)
    card.setScale(radius * 2.2)
    card.setBillboardPointEye()
    card.setTexture(texture)
    card.setLightOff(1)
    card.setDepthWrite(False)
    card.setBin("fixed", 20)
    card.setFogOff(1)
    card.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
    card.setColorScale(color[0] * 2, color[1] * 2, color[2] * 2, 1)
    return card

