"""Peligros del entorno que cambian el combate según la galaxia.

- Campo de energía (Nebulosa Carmesí): drena escudos y energía dentro.
- Anomalía antigua (Abismo): esfera que deriva y daña lo que toca.
- Grieta gravitatoria (Núcleo del Vacío): atrae las naves y daña en el centro.
"""
from __future__ import annotations

import math
import random

from panda3d.core import ColorBlendAttrib, NodePath, Point3, Vec3

from game.combat.damage import DamageInfo
from game.graphics.procedural import MeshBuilder, disc
from game.graphics.shaders import load_shader

PURE_ADD = ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne)


def _bubble(parent: NodePath, radius: float, color, intensity: float) -> NodePath:
    b = MeshBuilder()
    b.icosphere((0, 0, 0), 1.0, 3, (1, 1, 1, 1))
    node = b.build("hazard-bubble")
    node.reparentTo(parent)
    node.setScale(radius)
    node.setShader(load_shader("fresnel.vert", "shield.frag"))
    node.setShaderInput("cam_pos", Vec3(0, 0, 0))
    node.setShaderInput("shield_color", (*color, 1))
    node.setShaderInput("hit_dir", Vec3(0, 0, 0))
    node.setShaderInput("intensity", intensity)
    node.setShaderInput("center", Point3(0, 0, 0))
    node.setAttrib(PURE_ADD)
    node.setDepthWrite(False)
    node.setTwoSided(True)
    node.setBin("fixed", 8)
    return node


class Hazard:
    name = "peligro"
    alert = ""

    def __init__(self, parent: NodePath, pos: Point3, radius: float):
        self.root = parent.attachNewNode(self.name)
        self.root.setPos(pos)
        self.radius = radius
        self.bubble = None

    @property
    def pos(self) -> Point3:
        return self.root.getPos()

    def update(self, dt: float, cam_pos: Point3) -> None:
        if self.bubble is not None:
            self.bubble.setShaderInput("cam_pos", cam_pos)
            self.bubble.setShaderInput("center", self.pos)

    def affect(self, ship, dt: float) -> str | None:
        return None

    def destroy(self) -> None:
        self.root.removeNode()


class EnergyField(Hazard):
    name = "campo-energia"
    alert = "CAMPO DE ENERGÍA: escudos drenándose"

    def __init__(self, parent, pos, radius):
        super().__init__(parent, pos, radius)
        self.bubble = _bubble(self.root, radius, (1.0, 0.25, 0.4), 0.9)

    def affect(self, ship, dt):
        if (ship.pos - self.pos).length() > self.radius:
            return None
        ship.durability.shield = max(0.0, ship.durability.shield - 22 * dt)
        ship.durability.since_hit = 0.0
        if hasattr(ship, "energy"):
            ship.energy = max(0.0, ship.energy - 30 * dt)
        return self.alert


class Anomaly(Hazard):
    name = "anomalia"
    alert = "ANOMALÍA: radiación letal"

    def __init__(self, parent, pos, radius, rng: random.Random, arena: float):
        super().__init__(parent, pos, radius)
        self.bubble = _bubble(self.root, radius, (0.35, 1.0, 0.5), 1.1)
        self.rng = rng
        self.arena = arena
        self.velocity = Vec3(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-.3, .3)) * 18
        self.phase = rng.uniform(0, 6.28)

    def update(self, dt, cam_pos):
        super().update(dt, cam_pos)
        self.phase += dt
        p = self.pos + self.velocity * dt
        if p.length() > self.arena * 0.8:
            self.velocity = -self.velocity
        self.root.setPos(p)
        self.bubble.setScale(self.radius * (1 + 0.06 * math.sin(self.phase * 3)))

    def affect(self, ship, dt):
        if getattr(ship, "faction", "") == "enemy" and getattr(ship, "alien", False):
            return None
        if (ship.pos - self.pos).length() > self.radius:
            return None
        ship.apply_damage(DamageInfo(26 * dt, 1.0, 1.0), None, silent=True)
        return self.alert


class GravityRift(Hazard):
    name = "grieta"
    alert = "GRIETA GRAVITATORIA: ¡aléjate!"

    def __init__(self, parent, pos, radius):
        super().__init__(parent, pos, radius)
        self.bubble = _bubble(self.root, radius * 0.5, (0.7, 0.25, 1.0), 1.4)
        vortex = disc(radius * 1.2, 64, "rift")
        vortex.reparentTo(self.root)
        vortex.setBillboardPointEye()
        vortex.setShader(load_shader("portal.vert", "portal.frag"))
        vortex.setShaderInput("color_a", (0.5, 0.1, 0.9, 1))
        vortex.setShaderInput("color_b", (0.1, 0.0, 0.3, 1))
        vortex.setShaderInput("strength", 0.8)
        vortex.setAttrib(PURE_ADD)
        vortex.setDepthWrite(False)
        vortex.setTwoSided(True)
        vortex.setBin("fixed", 7)

    def affect(self, ship, dt):
        offset = self.pos - ship.pos
        dist = offset.length()
        pull_range = self.radius * 3.2
        if dist > pull_range or dist < 1e-3:
            return None
        offset.normalize()
        strength = (1 - dist / pull_range) * 70
        ship.velocity += offset * strength * dt
        if dist < self.radius * 0.5:
            ship.apply_damage(DamageInfo(35 * dt, 1.0, 1.0), None, silent=True)
        return self.alert


def build_hazards(base, parent: NodePath, cfg_list: list, arena: float, rng: random.Random) -> list:
    hazards = []
    for cfg in cfg_list:
        for _ in range(int(cfg.get("count", 1))):
            ang = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(arena * 0.3, arena * 0.8)
            pos = Point3(math.cos(ang) * dist, math.sin(ang) * dist, rng.uniform(-150, 150))
            radius = float(cfg.get("radius", 120))
            kind = cfg["type"]
            if kind == "energy_field":
                hazards.append(EnergyField(parent, pos, radius))
            elif kind == "anomaly":
                hazards.append(Anomaly(parent, pos, radius, rng, arena))
            elif kind == "gravity_rift":
                hazards.append(GravityRift(parent, pos, radius))
    return hazards
