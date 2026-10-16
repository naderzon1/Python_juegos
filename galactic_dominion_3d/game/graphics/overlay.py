"""Superposiciones a pantalla completa: salto hiperespacial y viñeta de daño."""
from __future__ import annotations

import numpy as np
from panda3d.core import CardMaker, TransparencyAttrib

from game.graphics.shaders import load_shader
from game.graphics.textures import make_texture


class Overlays:
    def __init__(self, base):
        self.base = base
        cm = CardMaker("hyperspace")
        cm.setFrameFullscreenQuad()
        self.jump = base.render2d.attachNewNode(cm.generate())
        self.jump.setShader(load_shader("portal.vert", "hyperspace.frag"))
        self.jump.setShaderInput("progress", 0.0)
        self.jump.setShaderInput("tint", (0.45, 0.75, 1.0, 1))
        self.jump.setTransparency(TransparencyAttrib.MAlpha)
        self.jump.setBin("fixed", 100)
        self.jump.setDepthTest(False)
        self.jump.setDepthWrite(False)
        self.jump.hide()
        size = 128
        y, x = np.mgrid[-1:1:size * 1j, -1:1:size * 1j]
        alpha = np.clip((np.sqrt(x * x + y * y) - 0.55) * 1.6, 0, 1) ** 1.5
        rgb = np.dstack([np.ones_like(x), np.full_like(x, 0.1), np.full_like(x, 0.08)])
        cm2 = CardMaker("damage")
        cm2.setFrameFullscreenQuad()
        self.damage = base.render2d.attachNewNode(cm2.generate())
        self.damage.setTexture(make_texture(rgb, "damage-vignette", alpha=alpha, mipmap=False))
        self.damage.setTransparency(TransparencyAttrib.MAlpha)
        self.damage.setBin("fixed", 90)
        self.damage.setDepthTest(False)
        self.damage.setDepthWrite(False)
        self.damage.setAlphaScale(0)
        self.damage.hide()
        self.damage_level = 0.0

    def set_jump(self, progress: float, tint=None) -> None:
        if progress <= 0.001:
            self.jump.hide()
            return
        self.jump.show()
        self.jump.setShaderInput("progress", min(1.0, progress))
        if tint is not None:
            self.jump.setShaderInput("tint", (*tint, 1))

    def pulse_damage(self, amount: float) -> None:
        self.damage_level = min(1.0, self.damage_level + amount)

    def update(self, dt: float, low_hull: bool) -> None:
        target = 0.35 if low_hull else 0.0
        self.damage_level = max(target, self.damage_level - dt * 1.5)
        if self.damage_level <= 0.01:
            self.damage.hide()
        else:
            self.damage.show()
            self.damage.setAlphaScale(self.damage_level)

    def clear(self) -> None:
        self.damage_level = 0.0
        self.damage.hide()
        self.jump.hide()
