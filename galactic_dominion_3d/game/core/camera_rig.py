"""Cámara de persecución dinámica.

Sigue a la nave con un pequeño retardo (las curvas se notan), abre el campo
de visión con la velocidad y el impulso, y vibra de forma moderada con los
impactos y explosiones cercanas (modelo de "trauma" que decae).
"""
from __future__ import annotations

import math
import random

from panda3d.core import Point3, Vec3


class ChaseCamera:
    def __init__(self, base, fov: float):
        self.base = base
        self.cam = base.camera
        self.base_fov = fov
        self.fov = fov
        self.trauma = 0.0
        self.offset = Vec3(0, -24, 6.5)
        self.first = True
        base.camLens.setNearFar(1.0, 90000.0)
        base.camLens.setFov(fov)

    def add_trauma(self, amount: float) -> None:
        self.trauma = min(1.0, self.trauma + amount)

    def update(self, dt: float, ship, speed_ratio: float, boosting: bool) -> None:
        render = self.base.render
        desired = render.getRelativePoint(ship.node, Point3(self.offset))
        if self.first:
            self.cam.setPos(desired)
            self.first = False
        else:
            k = 1.0 - math.exp(-dt * 7.5)
            pos = self.cam.getPos(render)
            self.cam.setPos(pos + (desired - pos) * k)
        fwd = render.getRelativeVector(ship.node, Vec3(0, 1, 0))
        up = render.getRelativeVector(ship.node, Vec3(0, 0, 1))
        self.cam.lookAt(ship.pos + fwd * 90 + up * 3, up)
        if self.trauma > 0:
            shake = self.trauma * self.trauma
            self.cam.setPos(self.cam, Vec3(random.uniform(-1, 1), random.uniform(-1, 1) * 0.3,
                                           random.uniform(-1, 1)) * shake * 1.4)
            self.cam.setHpr(self.cam, random.uniform(-1, 1) * shake * 0.8, random.uniform(-1, 1) * shake * 0.8, 0)
            self.trauma = max(0.0, self.trauma - dt * 1.4)
        target_fov = self.base_fov + speed_ratio * 7 + (9 if boosting else 0)
        self.fov += (target_fov - self.fov) * min(1.0, dt * 4)
        self.base.camLens.setFov(self.fov)

    def orbit(self, dt: float, center: Point3, distance: float, time: float) -> None:
        """Cámara cinemática alrededor de un punto (muerte del jugador, jefe derrotado)."""
        a = time * 0.35
        self.cam.setPos(center + Vec3(math.cos(a) * distance, math.sin(a) * distance, distance * 0.35))
        self.cam.lookAt(center)

    def reset(self) -> None:
        self.first = True
        self.trauma = 0.0
        self.fov = self.base_fov
        self.base.camLens.setFov(self.base_fov)
