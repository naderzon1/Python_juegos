"""Entidades del combate: cualquier cosa que puede recibir daño.

``Entity`` une un nodo 3D con un ``Durability`` y unas esferas de colisión.
``Ship`` añade velocidad, orientación, motores luminosos, burbuja de escudo
visible al recibir impactos, destellos y humo cuando el casco está dañado.
"""
from __future__ import annotations

import math
import random

from panda3d.core import ColorBlendAttrib, NodePath, Point3, Quat, Vec3

from game.combat.damage import DamageInfo, DamageResult, Durability
from game.graphics.effects import engine_sprite
from game.graphics.procedural import MeshBuilder
from game.graphics.shaders import load_shader
from game.graphics.textures import glow_texture

PURE_ADD = ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne)
_SHIELD_MESH = None
_GLOW = None


def shield_mesh() -> NodePath:
    global _SHIELD_MESH
    if _SHIELD_MESH is None:
        b = MeshBuilder()
        b.icosphere((0, 0, 0), 1.0, 3, (1, 1, 1, 1))
        _SHIELD_MESH = b.build("shield")
    return _SHIELD_MESH


def glow_tex():
    global _GLOW
    if _GLOW is None:
        _GLOW = glow_texture(64, 2.0)
    return _GLOW


class Entity:
    def __init__(self, world, node: NodePath, faction: str, durability: Durability, name: str, kind: str,
                 hit_spheres: list, bound_radius: float):
        self.world = world
        self.node = node
        self.faction = faction
        self.durability = durability
        self.name = name
        self.kind = kind
        self.hit_spheres = hit_spheres
        self.bound_radius = bound_radius
        self.velocity = Vec3(0, 0, 0)
        self.alive = True
        self.elite = False
        self.boss = False
        self.alien = False
        self.type_id = kind
        self.flash = 0.0
        self.shield_flash = 0.0
        self.shield_node: NodePath | None = None
        self.shield_color = (0.35, 0.75, 1.0)
        self.smoke_timer = 0.0
        self.last_hit_time = -99.0
        self.targetable = True
        self.hull_nodes: list[NodePath] = []

    # --- geometría ----------------------------------------------------------
    @property
    def pos(self) -> Point3:
        return self.node.getPos(self.world.render)

    def world_spheres(self) -> list:
        mat = self.node.getMat(self.world.render)
        scale = self.node.getScale(self.world.render).x
        return [(mat.xformPoint(p), r * scale) for p, r in self.hit_spheres]

    def forward(self) -> Vec3:
        v = self.world.render.getRelativeVector(self.node, Vec3(0, 1, 0))
        v.normalize()
        return v

    # --- daño ---------------------------------------------------------------
    def apply_damage(self, info: DamageInfo, point: Point3 | None, silent: bool = False) -> DamageResult:
        if not self.alive:
            return DamageResult()
        result = self.durability.apply(info)
        self.last_hit_time = self.world.time
        if not silent:
            if result.shield_damage > 0:
                self.show_shield_hit(point)
            if result.hull_damage > 0:
                self.flash = 0.12
        if result.destroyed:
            self.world.on_destroyed(self, info.source)
        return result

    def show_shield_hit(self, point: Point3 | None) -> None:
        if self.durability.max_shield <= 0:
            return
        if self.shield_node is None:
            node = shield_mesh().copyTo(self.node)
            scale = self.bound_radius * 1.25 / max(self.node.getScale(self.world.render).x, 1e-4)
            node.setScale(scale)
            node.setShader(load_shader("fresnel.vert", "shield.frag"))
            node.setShaderInput("shield_color", (*self.shield_color, 1))
            node.setShaderInput("intensity", 0.0)
            node.setShaderInput("hit_dir", Vec3(0, 0, 0))
            node.setShaderInput("cam_pos", Vec3(0, 0, 0))
            node.setShaderInput("center", Point3(0, 0, 0))
            node.setAttrib(PURE_ADD)
            node.setDepthWrite(False)
            node.setLightOff(1)
            node.setBin("fixed", 9)
            self.shield_node = node
        direction = Vec3(0, 0, 0)
        if point is not None:
            direction = point - self.pos
            if direction.length() > 1e-3:
                direction.normalize()
        self.shield_node.setShaderInput("hit_dir", direction)
        self.shield_flash = 0.35

    def update_visuals(self, dt: float) -> None:
        if self.flash > 0:
            self.flash -= dt
            k = 1.0 + max(0.0, self.flash) * 12
            for hull in self.hull_nodes:
                hull.setColorScale(k, k, k, 1)
            if self.flash <= 0:
                for hull in self.hull_nodes:
                    hull.clearColorScale()
        if self.shield_node is not None:
            if self.shield_flash > 0:
                self.shield_flash -= dt
                self.shield_node.show()
                k = 1.6 if self.bound_radius < 15 else 0.7  # las burbujas grandes, más tenues
                self.shield_node.setShaderInput("intensity", max(0.0, self.shield_flash) * k)
                self.shield_node.setShaderInput("cam_pos", self.world.camera_pos)
                self.shield_node.setShaderInput("center", self.pos)
            else:
                self.shield_node.hide()
        if self.durability.hull_ratio < 0.4 and self.alive:
            self.smoke_timer -= dt
            if self.smoke_timer <= 0:
                self.smoke_timer = 0.06 + self.durability.hull_ratio * 0.3
                r = self.bound_radius * 0.5
                offset = Vec3(random.uniform(-r, r), random.uniform(-r, r), random.uniform(-r, r))
                self.world.effects.smoke_puff(self.pos + offset, max(1.0, self.bound_radius * 0.25))

    def destroy(self) -> None:
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class Ship(Entity):
    """Entidad móvil con modelo de nave y toberas luminosas."""

    def __init__(self, world, model, faction: str, durability: Durability, name: str, kind: str,
                 max_speed: float, turn_rate: float):
        node = world.render.attachNewNode(name)
        model.root.reparentTo(node)
        spheres = model.hit_spheres or [(Point3(0, 0, 0), model.length * 0.45)]
        bound = max(p.length() + r for p, r in spheres)
        super().__init__(world, node, faction, durability, name, kind, spheres, bound)
        self.model = model
        self.max_speed = max_speed
        self.turn_rate = turn_rate
        self.throttle = 0.6
        self.hull_nodes = [model.hull]
        self.engine_cards = []
        tex = glow_tex()
        for pos, radius in model.engines:
            card = engine_sprite(model.root, pos, radius, model.glow_color, tex)
            self.engine_cards.append((card, radius))

    def update_engines(self, boost: float = 0.0) -> None:
        for card, radius in self.engine_cards:
            k = 0.55 + self.throttle * 0.6 + boost * 0.7 + random.uniform(-0.06, 0.06)
            card.setScale(radius * 1.5 * k)

    def turn_towards(self, direction: Vec3, dt: float, bank: float = 0.6) -> None:
        """Gira hacia ``direction`` sin superar ``turn_rate`` y se inclina en la curva."""
        if direction.length() < 1e-6:
            return
        desired = Vec3(direction)
        desired.normalize()
        fwd = self.forward()
        dot = max(-1.0, min(1.0, fwd.dot(desired)))
        angle = math.acos(dot)
        axis = fwd.cross(desired)
        if axis.length() < 1e-6:
            axis = self.world.render.getRelativeVector(self.node, Vec3(0, 0, 1))
        axis.normalize()
        step = min(angle, math.radians(self.turn_rate) * dt)
        q = Quat()
        q.setFromAxisAngleRad(step, axis)
        self.node.setQuat(self.world.render, self.node.getQuat(self.world.render) * q)
        # alabeo: el "arriba" tiende al eje Z del mundo más la inclinación de la curva
        up = self.world.render.getRelativeVector(self.node, Vec3(0, 0, 1))
        right = self.world.render.getRelativeVector(self.node, Vec3(1, 0, 0))
        turn_side = axis.dot(self.world.render.getRelativeVector(self.node, Vec3(0, 0, 1)))
        target_up = Vec3(0, 0, 1) + right * (-turn_side * bank * min(1.0, angle * 3))
        target_up -= fwd * target_up.dot(fwd)
        if target_up.length() > 1e-3:
            target_up.normalize()
            roll_err = math.atan2(right.dot(target_up), up.dot(target_up))
            q2 = Quat()
            q2.setFromAxisAngleRad(-roll_err * min(1.0, dt * 2.5), fwd)
            self.node.setQuat(self.world.render, self.node.getQuat(self.world.render) * q2)
