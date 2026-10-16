"""Construcción del escenario espacial de una galaxia a partir de sus datos.

El fondo (estrellas, nebulosas y sol) cuelga de un nodo que sigue a la
cámara, así parece infinitamente lejano. Los planetas, asteroides, restos y
estaciones están en el mundo y tienen paralaje real.

``build_steps`` es un generador: cada paso construye una parte y devuelve un
texto para la pantalla de carga. Así el salto entre galaxias se reparte en
varios fotogramas y la ventana no se congela.
"""
from __future__ import annotations

import math
import random

from panda3d.core import (AmbientLight, ColorBlendAttrib, CullFaceAttrib, DirectionalLight, Fog, Geom,
                          GeomNode, GeomPoints, GeomVertexData, GeomVertexFormat, GeomVertexWriter, NodePath,
                          OmniBoundingVolume, Point3, PointLight, TransparencyAttrib, Vec3)

from game.galaxies.hazards import build_hazards
from game.graphics import models
from game.graphics.effects import engine_sprite
from game.graphics.procedural import annulus, uv_sphere
from game.graphics.shaders import load_shader
from game.graphics.textures import cloud_texture, glow_texture, planet_texture, ring_texture

ADDITIVE = ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne)
PURE_ADD = ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne)


def direction(h: float, p: float) -> Vec3:
    h, p = math.radians(h), math.radians(p)
    return Vec3(-math.sin(h) * math.cos(p), math.cos(h) * math.cos(p), math.sin(p))


def point_cloud(points, colors, name: str) -> NodePath:
    vdata = GeomVertexData(name, GeomVertexFormat.getV3c4(), Geom.UHStatic)
    vdata.uncleanSetNumRows(len(points))
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    for p, c in zip(points, colors):
        vw.addData3(*p)
        cw.addData4(*c)
    prim = GeomPoints(Geom.UHStatic)
    prim.addConsecutiveVertices(0, len(points))
    geom = Geom(vdata)
    geom.addPrimitive(prim)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


class GalaxyScene:
    def __init__(self, base, galaxy: dict, quality: dict, mission: dict | None = None, seed: int | None = None):
        self.base = base
        self.galaxy = galaxy
        self.env = galaxy["environment"]
        self.quality = quality
        self.mission = mission or {}
        self.rng = random.Random(seed if seed is not None else hash(galaxy["id"]) & 0xFFFF)
        self.root = base.render.attachNewNode(f"galaxy-{galaxy['id']}")
        self.bg = base.render.attachNewNode("background")
        self.bg.setBin("background", 10)
        self.bg.setDepthWrite(False)
        self.bg.setDepthTest(False)
        self.bg.setLightOff(1)
        self.bg.setFogOff(1)
        self.lights: list[NodePath] = []
        self.sun_dir = Vec3(0, 1, -0.3)
        self.hazard_rocks: list[tuple[Point3, float]] = []
        self.planets: list[NodePath] = []
        self.planet_pivots: list[NodePath] = []
        self.moons: list[tuple[NodePath, float]] = []
        self.atmospheres: list[NodePath] = []
        self.hazards = []
        self.portal = None
        self.portal_disc = None
        self.station_decor = None
        self.dust = None
        self.arena_radius = float(galaxy.get("arena_radius", 1600))
        self.portal_pos = Point3(0, self.arena_radius * 0.85, 60)
        self.sun_np = None

    # --- construcción por pasos ---------------------------------------------
    def build_steps(self):
        yield "Calibrando sensores de largo alcance"
        self._lights()
        yield "Cartografiando estrellas"
        self._stars()
        yield "Modelando nebulosas"
        self._nebulae()
        for i, pcfg in enumerate(self.env.get("planets", [])):
            yield f"Generando planeta {i + 1}"
            self._planet(pcfg, i)
        yield "Situando campos de asteroides"
        self._asteroids()
        yield "Dispersando restos de naves"
        self._debris()
        yield "Activando balizas y estructuras"
        self._structures()
        yield "Escaneando anomalías"
        self.hazards = build_hazards(self.base, self.root, self.env.get("hazards", []), self.arena_radius, self.rng)
        yield "Listo para el salto"

    def build_all(self) -> None:
        for _ in self.build_steps():
            pass

    def _lights(self) -> None:
        env = self.env
        self.base.setBackgroundColor(*env["bg_color"], 1)
        sun = DirectionalLight("sun")
        k = float(env["sun"].get("intensity", 1.3))
        sun.setColor((env["sun"]["color"][0] * k, env["sun"]["color"][1] * k, env["sun"]["color"][2] * k, 1))
        sun_np = self.root.attachNewNode(sun)
        sun_np.setHpr(*env["sun"]["hpr"])
        if self.quality.get("shadows"):
            sun.setShadowCaster(True, 2048, 2048)
            lens = sun.getLens()
            lens.setFilmSize(260, 260)
            lens.setNearFar(-600, 600)
        self.base.render.setLight(sun_np)
        self.sun_np = sun_np
        self.lights.append(sun_np)
        self.sun_dir = self.base.render.getRelativeVector(sun_np, Vec3(0, 1, 0))
        self.sun_dir.normalize()
        # luz de relleno opuesta al sol, teñida por la nebulosa: las naves en sombra no quedan
        # como siluetas negras sobre el fondo
        neb = env["nebula_colors"][0]
        fill = DirectionalLight("fill")
        fill.setColor((0.12 + neb[0] * 0.35, 0.12 + neb[1] * 0.35, 0.14 + neb[2] * 0.35, 1))
        fill_np = self.root.attachNewNode(fill)
        fill_np.lookAt(Point3(-self.sun_dir.x, -self.sun_dir.y, -self.sun_dir.z))
        self.base.render.setLight(fill_np)
        self.lights.append(fill_np)
        amb = AmbientLight("ambient")
        amb.setColor((max(0.1, env["ambient"][0]), max(0.1, env["ambient"][1]), max(0.12, env["ambient"][2]), 1))
        amb_np = self.root.attachNewNode(amb)
        self.base.render.setLight(amb_np)
        self.lights.append(amb_np)
        fog_cfg = env.get("fog")
        if fog_cfg:
            fog = Fog("galaxy-fog")
            fog.setColor(*fog_cfg["color"])
            fog.setExpDensity(float(fog_cfg["density"]))
            self.base.render.setFog(fog)
        # disco solar y corona en el fondo, opuestos a la dirección de la luz
        glow = glow_texture(128, 1.6)
        sun_pos = -self.sun_dir * 30000
        c = env["sun"]["color"]
        for size, power in ((900, 6.0), (2600, 2.2), (7000, 0.9)):
            card = engine_sprite(self.bg, sun_pos, size, (c[0] * power / 2, c[1] * power / 2, c[2] * power / 2), glow)
            card.setBin("background", 12)

    def _stars(self) -> None:
        count = int(self.quality.get("star_count", 3000))
        tint = self.env["star_tint"]
        layers = ((0.6, 1.0, 0.55), (0.3, 2.0, 0.85), (0.1, 3.0, 1.0))
        palette = [(1, 1, 1), (1, .92, .8), (.8, .88, 1), (1, .8, .75), tuple(tint)]
        for share, size, bright in layers:
            pts, cols = [], []
            for _ in range(int(count * share)):
                v = Vec3(self.rng.gauss(0, 1), self.rng.gauss(0, 1), self.rng.gauss(0, 1))
                v.normalize()
                pts.append(v * 40000)
                c = self.rng.choice(palette)
                b = bright * self.rng.uniform(.5, 1.0)
                cols.append((c[0] * tint[0] * b, c[1] * tint[1] * b, c[2] * tint[2] * b, 1))
            layer = point_cloud(pts, cols, "stars")
            layer.reparentTo(self.bg)
            layer.setRenderModeThickness(size)
            layer.setBin("background", 11)
        glow = glow_texture(64, 2.4)
        for _ in range(int(count * 0.012)):
            v = Vec3(self.rng.gauss(0, 1), self.rng.gauss(0, 1), self.rng.gauss(0, 1))
            v.normalize()
            c = self.rng.choice(palette)
            card = engine_sprite(self.bg, v * 39000, self.rng.uniform(60, 160), (c[0] * .8, c[1] * .8, c[2] * .8), glow)
            card.setBin("background", 12)
        # polvo espacial cercano (shader que repite los puntos alrededor de la cámara)
        dust_count = int(self.quality.get("dust_count", 400))
        box = 420.0
        pts = [(self.rng.uniform(0, box), self.rng.uniform(0, box), self.rng.uniform(0, box)) for _ in range(dust_count)]
        cols = [(tint[0] * .6, tint[1] * .6, tint[2] * .7, self.rng.uniform(.3, .8)) for _ in range(dust_count)]
        dust = point_cloud(pts, cols, "dust")
        dust.reparentTo(self.base.render)
        dust.setShader(load_shader("dust.vert", "dust.frag"))
        dust.setShaderInput("cam_pos", Vec3(0, 0, 0))
        dust.setShaderInput("box_size", box)
        dust.setRenderModeThickness(2)
        dust.setAttrib(PURE_ADD)
        dust.setDepthWrite(False)
        dust.setBin("fixed", 5)
        dust.node().setBounds(OmniBoundingVolume())
        dust.node().setFinal(True)
        self.dust = dust

    def _nebulae(self) -> None:
        colors = self.env["nebula_colors"]
        n = int(self.quality.get("nebula_sprites", 18))
        textures = [cloud_texture(s) for s in (3, 7, 11, 19)]
        clusters = []
        for _ in range(3):
            v = Vec3(self.rng.gauss(0, 1), self.rng.gauss(0, 1), self.rng.gauss(0, .5))
            v.normalize()
            clusters.append(v)
        root = self.bg.attachNewNode("nebulae")
        root.setBin("background", 13)
        for i in range(n):
            base_dir = clusters[i % len(clusters)]
            jitter = Vec3(self.rng.gauss(0, .28), self.rng.gauss(0, .28), self.rng.gauss(0, .2))
            d = base_dir + jitter
            d.normalize()
            c = colors[self.rng.randrange(len(colors))]
            mixc = colors[self.rng.randrange(len(colors))]
            k = self.rng.uniform(.25, .55) * (1.4 if i % 5 == 0 else 1)
            col = ((c[0] + mixc[0]) * .5 * k, (c[1] + mixc[1]) * .5 * k, (c[2] + mixc[2]) * .5 * k)
            card = engine_sprite(root, d * 34000, self.rng.uniform(5000, 13000), col, self.rng.choice(textures))
            card.setR(self.rng.uniform(0, 360))
            card.setBin("background", 13)

    def _planet(self, pcfg: dict, index: int) -> None:
        radius = float(pcfg["radius"])
        pos = direction(pcfg["h"], pcfg["p"]) * float(pcfg["distance"])
        pivot = self.root.attachNewNode(f"planet-{index}")
        pivot.setPos(pos)
        pivot.setFogOff(1)
        body = uv_sphere(radius, 56, 112, "planet")
        body.reparentTo(pivot)
        size = int(self.quality.get("planet_texture", 512))
        body.setTexture(planet_texture(pcfg["kind"], pcfg["palette"], size, seed=index * 31 + len(self.galaxy["id"])))
        mat = models.hull_material(8, 0.12)
        body.setMaterial(mat)
        body.setHpr(self.rng.uniform(0, 360), self.rng.uniform(-20, 20), self.rng.uniform(-10, 10))
        self.planets.append(body)
        atmo = pcfg.get("atmosphere")
        if atmo:
            shader = load_shader("fresnel.vert", "atmosphere.frag")
            for scale, power, strength, reverse in ((1.07, 2.4, 1.3, True), (1.012, 3.5, 0.9, False)):
                shell = uv_sphere(radius * scale, 40, 80, "atmosphere")
                shell.reparentTo(pivot)
                shell.setShader(shader)
                shell.setShaderInput("cam_pos", Vec3(0, 0, 0))
                shell.setShaderInput("sun_dir", self.sun_dir)
                shell.setShaderInput("atmo_color", (atmo[0], atmo[1], atmo[2], strength))
                shell.setShaderInput("power", power)
                shell.setAttrib(PURE_ADD)
                shell.setDepthWrite(False)
                shell.setBin("fixed", 3)
                if reverse:
                    shell.setAttrib(CullFaceAttrib.makeReverse())
                self.atmospheres.append(shell)
        if pcfg.get("rings"):
            ring = annulus(radius * 1.35, radius * 2.35, 160, "rings")
            ring.reparentTo(pivot)
            ring.setTexture(ring_texture(pcfg["palette"], seed=index + 5))
            ring.setTransparency(TransparencyAttrib.MAlpha)
            ring.setTwoSided(True)
            ring.setDepthWrite(False)
            ring.setLightOff(1)
            sc = self.env["sun"]["color"]
            ring.setColorScale(sc[0] * 1.1, sc[1] * 1.1, sc[2] * 1.1, 0.9)
            ring.setHpr(self.rng.uniform(0, 180), self.rng.uniform(55, 80), 0)
            ring.setBin("fixed", 4)
        for m in range(int(pcfg.get("moons", 0))):
            orbit = pivot.attachNewNode("moon-orbit")
            orbit.setHpr(self.rng.uniform(0, 360), self.rng.uniform(-25, 25), 0)
            moon = uv_sphere(radius * self.rng.uniform(.08, .18), 24, 48, "moon")
            moon.reparentTo(orbit)
            moon.setPos(radius * self.rng.uniform(2.6, 3.8), 0, 0)
            pal = [[.25, .24, .23], [.5, .48, .45], [.75, .73, .7]]
            moon.setTexture(planet_texture("rocky", pal, 128, seed=m * 7 + index))
            moon.setMaterial(mat)
            self.moons.append((orbit, self.rng.uniform(.4, 1.2)))
        self.planet_pivots.append(pivot)

    def _asteroids(self) -> None:
        cfg = self.env.get("asteroids", {})
        mult = float(self.quality.get("asteroid_mult", 1.0))
        templates = [models.build_asteroid(s) for s in range(6)]
        decor = self.root.attachNewNode("asteroids-decor")
        for i in range(int(cfg.get("decor", 0) * mult)):
            ang = self.rng.uniform(0, 2 * math.pi)
            dist = self.rng.uniform(self.arena_radius * 1.15, self.arena_radius * 3.2)
            node = self.rng.choice(templates).copyTo(decor)
            node.setPos(math.cos(ang) * dist, math.sin(ang) * dist, self.rng.uniform(-500, 500))
            node.setScale(self.rng.uniform(10, 140))
            node.setHpr(self.rng.uniform(0, 360), self.rng.uniform(0, 360), self.rng.uniform(0, 360))
        decor.flattenStrong()
        hazard = self.root.attachNewNode("asteroids-field")
        for i in range(int(cfg.get("hazard", 0) * mult)):
            for _ in range(10):
                p = Point3(self.rng.uniform(-1, 1), self.rng.uniform(-1, 1), self.rng.uniform(-.35, .35)) * \
                    self.arena_radius * .85
                if p.length() > 220:
                    break
            r = self.rng.uniform(12, 48)
            node = self.rng.choice(templates).copyTo(hazard)
            node.setPos(p)
            node.setScale(r)
            node.setHpr(self.rng.uniform(0, 360), self.rng.uniform(0, 360), 0)
            self.hazard_rocks.append((p, r * 0.92))
        hazard.flattenStrong()

    def _debris(self) -> None:
        group = self.root.attachNewNode("debris")
        for i in range(int(self.env.get("debris", 0))):
            node = models.build_debris(self.rng.randrange(1000))
            node.reparentTo(group)
            ang = self.rng.uniform(0, 2 * math.pi)
            dist = self.rng.uniform(300, self.arena_radius * 1.3)
            node.setPos(math.cos(ang) * dist, math.sin(ang) * dist, self.rng.uniform(-250, 250))
            node.setScale(self.rng.uniform(1.0, 3.5))
            node.setHpr(self.rng.uniform(0, 360), self.rng.uniform(0, 360), self.rng.uniform(0, 360))
        group.flattenStrong()

    def _structures(self) -> None:
        portal, disc = models.build_portal(70, (0.4, 0.8, 1.0))
        portal.reparentTo(self.root)
        portal.setPos(self.portal_pos)
        portal.lookAt(Point3(0, 0, 60))
        disc.setShader(load_shader("portal.vert", "portal.frag"))
        colors = self.env["nebula_colors"]
        disc.setShaderInput("color_a", (*colors[0], 1))
        disc.setShaderInput("color_b", (0.6, 0.9, 1.0, 1))
        disc.setShaderInput("strength", 0.25)
        disc.setAttrib(PURE_ADD)
        disc.setDepthWrite(False)
        disc.setBin("fixed", 6)
        self.portal, self.portal_disc = portal, disc
        # fuente de luz localizada: el portal ilumina las naves que se le acercan
        glow = PointLight("portal-light")
        glow.setColor((0.6, 1.1, 1.6, 1))
        glow.setAttenuation((1.0, 0.0, 0.000006))
        glow_np = self.root.attachNewNode(glow)
        glow_np.setPos(self.portal_pos)
        self.base.render.setLight(glow_np)
        self.lights.append(glow_np)
        if self.env.get("station") and self.mission.get("type") != "defend_station":
            station = models.build_station(True).root
            station.reparentTo(self.root)
            station.setPos(-700, 950, -120)
            station.setHpr(30, 20, 0)
            self.station_decor = station

    def set_portal_strength(self, value: float) -> None:
        if self.portal_disc is not None:
            self.portal_disc.setShaderInput("strength", value)

    # --- actualización ------------------------------------------------------
    def update(self, dt: float, cam_pos: Point3, focus: Point3) -> None:
        self.bg.setPos(cam_pos)
        if self.dust is not None:
            self.dust.setShaderInput("cam_pos", cam_pos)
        for shell in self.atmospheres:
            shell.setShaderInput("cam_pos", cam_pos)
        for body in self.planets:
            body.setH(body.getH() + dt * 0.4)
        for orbit, speed in self.moons:
            orbit.setH(orbit.getH() + dt * speed)
        if self.station_decor is not None:
            self.station_decor.setH(self.station_decor.getH() + dt * 2)
        if self.sun_np is not None and self.quality.get("shadows"):
            self.sun_np.setPos(focus)
        for hazard in self.hazards:
            hazard.update(dt, cam_pos)

    def destroy(self) -> None:
        for light in self.lights:
            self.base.render.clearLight(light)
        self.base.render.clearFog()
        for hazard in self.hazards:
            hazard.destroy()
        self.root.removeNode()
        self.bg.removeNode()
        if self.dust is not None:
            self.dust.removeNode()
