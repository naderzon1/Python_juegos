"""Aliados de misión: estación a defender y carguero a escoltar."""
from __future__ import annotations

from panda3d.core import Point3, Vec3

from game.combat.damage import Durability
from game.graphics import models
from game.ships.entity import Entity, Ship


class AllyStation(Entity):
    def __init__(self, world, pos: Point3, hull: float, name: str = "Estación Orión-7"):
        model = models.build_station(True)
        node = world.render.attachNewNode("ally-station")
        model.root.reparentTo(node)
        node.setPos(pos)
        node.setHpr(20, 15, 0)
        bound = max(p.length() + r for p, r in model.hit_spheres)
        super().__init__(world, node, "player", Durability(hull, hull * 0.4, hull * 0.01, 6.0), name, "ally",
                         model.hit_spheres, bound)
        self.model = model
        self.hull_nodes = [model.hull]
        self.shield_color = (0.4, 0.8, 1.0)

    def update(self, dt: float) -> None:
        self.node.setH(self.node.getH() + dt * 2)
        self.durability.update(dt)
        self.update_visuals(dt)


class Freighter(Ship):
    def __init__(self, world, start: Point3, goal: Point3, speed: float, hull: float):
        model = models.build_freighter()
        super().__init__(world, model, "player", Durability(hull, hull * 0.3, hull * 0.01, 5.0),
                         "Carguero Esperanza", "ally", speed, 10)
        self.node.setPos(start)
        self.node.lookAt(goal)
        self.start = Point3(start)
        self.goal = Point3(goal)
        self.shield_color = (0.4, 0.8, 1.0)
        self.throttle = 0.6

    @property
    def travelled(self) -> float:
        return (self.pos - self.start).length()

    def update(self, dt: float) -> None:
        to_goal = self.goal - self.pos
        if to_goal.length() > 5:
            to_goal.normalize()
            self.velocity = to_goal * self.max_speed
            self.node.setPos(self.pos + self.velocity * dt)
        else:
            self.velocity = Vec3(0, 0, 0)
        self.durability.update(dt)
        self.update_engines()
        self.update_visuals(dt)


class SalvagePod:
    """Contenedor flotante que se recoge acercándose (con imán a corta distancia)."""

    def __init__(self, render, pos: Point3, color=(0.4, 1.0, 0.8)):
        self.node = models.build_salvage_pod(color)
        self.node.reparentTo(render)
        self.node.setPos(pos)
        self.node.setScale(1.6)
        self.collected = False

    @property
    def pos(self) -> Point3:
        return self.node.getPos()

    def update(self, dt: float, player_pos: Point3) -> bool:
        """Devuelve True cuando el jugador lo recoge."""
        if self.collected:
            return False
        self.node.setHpr(self.node.getH() + dt * 40, self.node.getP() + dt * 25, 0)
        offset = player_pos - self.pos
        dist = offset.length()
        if dist < 32:
            self.collected = True
            self.node.removeNode()
            return True
        if dist < 170:  # imán: el contenedor se acerca cada vez más rápido
            offset.normalize()
            self.node.setPos(self.pos + offset * (180 - dist) * dt * 2.2)
        return False

    def destroy(self) -> None:
        if not self.node.isEmpty():
            self.node.removeNode()
