"""Postproceso propio: escena HDR en búfer de coma flotante, bloom en dos
escalas, mapeo de tonos filmico (aproximación ACES) y viñeta.

Se apoya en ``FilterManager`` de Panda3D. Si la tarjeta gráfica no permite
crear los búferes, se desactiva sin romper el juego (``self.enabled = False``).
"""
from __future__ import annotations

from direct.filter.FilterManager import FilterManager
from panda3d.core import FrameBufferProperties, SamplerState, Texture

from game.graphics.shaders import load_shader


def _tex(name: str) -> Texture:
    tex = Texture(name)
    tex.setWrapU(SamplerState.WM_clamp)
    tex.setWrapV(SamplerState.WM_clamp)
    tex.setMinfilter(SamplerState.FT_linear)
    tex.setMagfilter(SamplerState.FT_linear)
    return tex


class PostFX:
    def __init__(self, base, msaa: int = 0, bloom: bool = True):
        self.base = base
        self.enabled = False
        self.manager = None
        self.error = ""
        self.final = None
        if not bloom:
            return
        try:
            self._build(msaa)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo de GPU desactiva el efecto
            self.error = str(exc)
            self.cleanup()

    def _build(self, msaa: int) -> None:
        manager = FilterManager(self.base.win, self.base.cam)
        self.manager = manager
        props = FrameBufferProperties()
        props.setFloatColor(True)
        props.setRgbaBits(16, 16, 16, 0)
        if msaa:
            props.setMultisamples(msaa)
        scene = _tex("pfx-scene")
        final = manager.renderSceneInto(colortex=scene, fbprops=props, clamping=False)
        if final is None and msaa:
            props.setMultisamples(0)
            final = manager.renderSceneInto(colortex=scene, fbprops=props, clamping=False)
        if final is None:
            raise RuntimeError("no se pudo crear el búfer HDR")
        quad_vs = "quad.vert"
        float_props = FrameBufferProperties()
        float_props.setFloatColor(True)
        float_props.setRgbaBits(16, 16, 16, 0)

        bright_tex = _tex("pfx-bright")
        bright = manager.renderQuadInto("pfx-bright", div=2, colortex=bright_tex, fbprops=float_props)
        bright.setShader(load_shader(quad_vs, "bright.frag"))
        bright.setShaderInput("src", scene)
        bright.setShaderInput("threshold", 0.82)

        def blur(src, name, div, direction):
            tex = _tex(name)
            quad = manager.renderQuadInto(name, div=div, colortex=tex, fbprops=float_props)
            quad.setShader(load_shader(quad_vs, "blur.frag"))
            quad.setShaderInput("src", src)
            quad.setShaderInput("direction", direction)
            return tex

        a = blur(bright_tex, "pfx-bh4", 4, (1.0, 0.0))
        a = blur(a, "pfx-bv4", 4, (0.0, 1.0))
        b = blur(a, "pfx-bh8", 8, (1.6, 0.0))
        b = blur(b, "pfx-bv8", 8, (0.0, 1.6))
        final.setShader(load_shader(quad_vs, "composite.frag"))
        final.setShaderInput("scene", scene)
        final.setShaderInput("bloom_a", a)
        final.setShaderInput("bloom_b", b)
        final.setShaderInput("bloom_strength", 1.0)
        final.setShaderInput("exposure", 1.12)
        final.setShaderInput("vignette", 0.55)
        self.final = final
        self.enabled = True

    def set_bloom_strength(self, value: float) -> None:
        if self.final is not None:
            self.final.setShaderInput("bloom_strength", value)

    def cleanup(self) -> None:
        if self.manager is not None:
            self.manager.cleanup()
            self.manager = None
        self.enabled = False
        self.final = None
