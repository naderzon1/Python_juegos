"""Visor de modelos procedurales.

Uso:
    python tools/model_viewer.py               # ventana interactiva (ratón: orbitar con el botón izquierdo)
    python tools/model_viewer.py captura.png   # renderiza una imagen y sale
    python tools/model_viewer.py captura.png 0 # igual, enfocando el modelo número 0
    python tools/model_viewer.py captura.png --tiers vanguard   # las cinco etapas Mk I-V
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from direct.showbase.ShowBase import ShowBase  # noqa: E402
from panda3d.core import (AmbientLight, DirectionalLight, Filename, Point3, Vec3,  # noqa: E402
                          loadPrcFileData)

from game.core.config import GameConfig  # noqa: E402
from game.graphics import models  # noqa: E402
from game.graphics.postfx import PostFX  # noqa: E402

loadPrcFileData("", "window-title Galactic Dominion 3D - visor de modelos\nwin-size 1600 900\n"
                    "framebuffer-multisample 1\nmultisamples 4\ntextures-power-2 none\nsync-video 0")


class Viewer(ShowBase):
    def __init__(self, shot: str | None, focus: int | None = None, tiers: str | None = None):
        super().__init__()
        cfg = GameConfig()
        self.setBackgroundColor(0.02, 0.025, 0.05, 1)
        self.render.setShaderAuto()
        sun = DirectionalLight("sun")
        sun.setColor((1.5, 1.42, 1.3, 1))
        sun_np = self.render.attachNewNode(sun)
        sun_np.setHpr(35, -35, 0)
        self.render.setLight(sun_np)
        amb = AmbientLight("amb")
        amb.setColor((0.12, 0.13, 0.18, 1))
        self.render.setLight(self.render.attachNewNode(amb))
        items = []
        if tiers:  # las cinco etapas de evolución de la nave elegida
            for tier in range(1, 6):
                items.append(models.build_player_ship(cfg.ships[tiers]["model"], tier=tier).root)
        else:
            for sid, ship in cfg.ships.items():
                items.append(models.build_player_ship(ship["model"]).root)
            for eid, enemy in cfg.enemies.items():
                if enemy["model"]["hull"] != "station":
                    items.append(models.build_enemy_ship(enemy["model"]).root)
        x = -len(items) * 9
        for node in items:
            node.reparentTo(self.render)
            node.setPos(x, 0, 0)
            node.setH(-35)
            x += 18 + node.getBounds().getRadius() * 0.4
        if tiers:
            self.disableMouse()
            for i, node in enumerate(items):
                node.setPos((i - 2) * 13.5, 0, 0)
                node.setHpr(160, 0, 0)
            self.camera.setPos(0, -30, 26)
            self.camera.lookAt(Point3(0, 0, -1))
            self.camLens.setFov(75)
            sun_np.setHpr(150, -50, 0)
            self._finish(shot)
            return
        boss = models.build_boss(cfg.bosses["iron_dreadnought"]["model"], 48, 5).root
        boss.reparentTo(self.render)
        boss.setPos(0, 220, -40)
        boss.setH(-60)
        station = models.build_enemy_ship(cfg.enemies["sentinel_station"]["model"]).root
        station.reparentTo(self.render)
        station.setPos(-170, 300, 30)
        self.disableMouse()
        self.camera.setPos(0, -95, 35)
        self.camera.lookAt(Point3(0, 60, -5))
        if focus is not None:
            target = items[focus]
            size = target.getBounds().getRadius()
            self.camera.setPos(target.getPos() + Vec3(size * 1.1, -size * 1.9, size * 0.9))
            self.camera.lookAt(target)
        self.camLens.setFov(70)
        self.camLens.setNearFar(1, 5000)
        self._finish(shot)

    def _finish(self, shot):
        self.fx = PostFX(self, msaa=4, bloom=True)
        print("postfx:", self.fx.enabled, self.fx.error)
        if shot:
            for _ in range(3):
                self.graphicsEngine.renderFrame()
            self.win.saveScreenshot(Filename.fromOsSpecific(shot))
            print("captura:", shot)
            sys.exit(0)


if __name__ == "__main__":
    args = sys.argv[1:]
    tiers = None
    if "--tiers" in args:
        i = args.index("--tiers")
        tiers = args[i + 1] if i + 1 < len(args) else "vanguard"
        del args[i:i + 2]
    Viewer(args[0] if args else None, int(args[1]) if len(args) > 1 else None, tiers).run()
