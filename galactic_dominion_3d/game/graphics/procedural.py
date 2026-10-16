"""Construcción de mallas procedurales para Panda3D.

``MeshBuilder`` acumula triángulos con normales planas (aspecto facetado de
ciencia ficción), color por cara y coordenadas UV por proyección de caja para
que la textura de paneles se vea en todas las superficies. Ofrece piezas de
alto nivel: cajas, cilindros, placas (alas, aletas), secciones solevadas
(fuselajes) e icosferas deformadas (asteroides, cristales).

Convención de ejes de Panda3D: X derecha, Y adelante, Z arriba.
"""
from __future__ import annotations

import math
import random

from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter,
                          NodePath, Point3, Vec3)

Color = tuple


def _v(p) -> Vec3:
    return Vec3(p[0], p[1], p[2])


class MeshBuilder:
    def __init__(self, uv_scale: float = 0.25, jitter: float = 0.0, seed: int = 0):
        self.verts: list = []
        self.uv_scale = uv_scale
        self.jitter = jitter
        self.rng = random.Random(seed)

    # --- primitivas ----------------------------------------------------------
    def _shade(self, color: Color) -> Color:
        if not self.jitter:
            return color
        k = 1.0 + self.rng.uniform(-self.jitter, self.jitter)
        return (min(1, color[0] * k), min(1, color[1] * k), min(1, color[2] * k), color[3] if len(color) > 3 else 1)

    def tri(self, a, b, c, color: Color, away=None) -> None:
        a, b, c = _v(a), _v(b), _v(c)
        normal = (b - a).cross(c - a)
        if normal.length() < 1e-9:
            return
        normal.normalize()
        if away is not None:
            centroid = (a + b + c) / 3.0
            if normal.dot(centroid - _v(away)) < 0:
                b, c = c, b
                normal = -normal
        col = self._shade(color)
        ax = max(range(3), key=lambda i: abs(normal[i]))
        for p in (a, b, c):
            if ax == 0:
                uv = (p.y, p.z)
            elif ax == 1:
                uv = (p.x, p.z)
            else:
                uv = (p.x, p.y)
            self.verts.append((p, normal, col, (uv[0] * self.uv_scale, uv[1] * self.uv_scale)))

    def quad(self, a, b, c, d, color: Color, away=None) -> None:
        col = self._shade(color)
        saved, self.jitter = self.jitter, 0.0
        self.tri(a, b, c, col, away)
        self.tri(a, c, d, col, away)
        self.jitter = saved

    def box(self, center, size, color: Color, rot_h: float = 0.0) -> None:
        cx, cy, cz = center
        sx, sy, sz = size[0] / 2, size[1] / 2, size[2] / 2
        ch, sh = math.cos(math.radians(rot_h)), math.sin(math.radians(rot_h))

        def p(x, y, z):
            return (cx + x * ch - y * sh, cy + x * sh + y * ch, cz + z)

        corners = [p(x, y, z) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        for f in faces:
            self.quad(*(corners[i] for i in f), color, away=center)

    def cylinder(self, p0, p1, r0: float, r1: float, segments: int, color: Color, cap0=True, cap1=True,
                 cap_color: Color | None = None) -> None:
        p0, p1 = _v(p0), _v(p1)
        axis = p1 - p0
        length = axis.length()
        if length < 1e-6:
            return
        axis /= length
        helper = Vec3(0, 0, 1) if abs(axis.z) < 0.9 else Vec3(1, 0, 0)
        u = axis.cross(helper)
        u.normalize()
        w = axis.cross(u)
        ring0, ring1 = [], []
        for i in range(segments):
            ang = 2 * math.pi * i / segments
            offset = u * math.cos(ang) + w * math.sin(ang)
            ring0.append(p0 + offset * r0)
            ring1.append(p1 + offset * r1)
        mid = (p0 + p1) / 2
        for i in range(segments):
            j = (i + 1) % segments
            local_mid = (p0 + p1) / 2 if r0 == r1 else mid
            self.quad(ring0[i], ring0[j], ring1[j], ring1[i], color, away=local_mid)
        cap_color = cap_color or color
        if cap0:
            for i in range(segments):
                self.tri(p0, ring0[i], ring0[(i + 1) % segments], cap_color, away=p1)
        if cap1:
            for i in range(segments):
                self.tri(p1, ring1[i], ring1[(i + 1) % segments], cap_color, away=p0)

    def plate(self, outline, normal, thickness: float, color: Color, edge_color: Color | None = None) -> None:
        """Placa gruesa a partir de un contorno plano convexo (alas, aletas, paneles solares)."""
        n = _v(normal)
        n.normalize()
        half = n * (thickness / 2)
        pts = [_v(p) for p in outline]
        center = sum(pts, Vec3(0, 0, 0)) / len(pts)
        top = [p + half for p in pts]
        bottom = [p - half for p in pts]
        for i in range(1, len(pts) - 1):
            self.tri(top[0], top[i], top[i + 1], color, away=center - n * 10)
            self.tri(bottom[0], bottom[i], bottom[i + 1], color, away=center + n * 10)
        edge_color = edge_color or color
        for i in range(len(pts)):
            j = (i + 1) % len(pts)
            self.quad(top[i], top[j], bottom[j], bottom[i], edge_color, away=center)

    def loft(self, sections: list, color, cap_front=True, cap_back=True) -> None:
        """Une secciones transversales (mismo número de puntos) en una superficie.

        ``color`` puede ser un color fijo o una función ``f(i_seccion, j_lado) -> color``.
        """
        rings = [[_v(p) for p in sec] for sec in sections]
        count = len(rings[0])
        centers = [sum(r, Vec3(0, 0, 0)) / count for r in rings]
        for i in range(len(rings) - 1):
            axis_mid = (centers[i] + centers[i + 1]) / 2
            for j in range(count):
                k = (j + 1) % count
                col = color(i, j) if callable(color) else color
                self.quad(rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j], col, away=axis_mid)
        first_col = color(0, 0) if callable(color) else color
        last_col = color(len(rings) - 2, 0) if callable(color) else color
        if cap_back:
            for j in range(count):
                self.tri(centers[0], rings[0][j], rings[0][(j + 1) % count], first_col, away=centers[1])
        if cap_front:
            for j in range(count):
                self.tri(centers[-1], rings[-1][j], rings[-1][(j + 1) % count], last_col, away=centers[-2])

    def icosphere(self, center, radius: float, subdiv: int, color: Color, roughness: float = 0.0,
                  stretch=(1, 1, 1), seed: int = 0) -> None:
        verts, faces = icosphere_data(subdiv)
        rng = random.Random(seed)
        bumps = [(_v((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))), rng.uniform(0.3, 1.0))
                 for _ in range(6)]
        c = _v(center)
        out = []
        for v in verts:
            d = Vec3(*v)
            k = 1.0
            if roughness:
                k += sum(math.sin(d.dot(b) * 3.1 + w * 5) * 0.5 for b, w in bumps) / len(bumps) * roughness
                k += rng.uniform(-0.5, 0.5) * roughness * 0.4
            out.append(c + Vec3(d.x * stretch[0], d.y * stretch[1], d.z * stretch[2]) * radius * k)
        for a, b, d in faces:
            self.tri(out[a], out[b], out[d], color, away=c)

    def merge(self, other: "MeshBuilder") -> None:
        self.verts.extend(other.verts)

    # --- salida --------------------------------------------------------------
    def build(self, name: str = "mesh") -> NodePath:
        fmt = GeomVertexFormat.getV3n3c4t2()
        vdata = GeomVertexData(name, fmt, Geom.UHStatic)
        vdata.uncleanSetNumRows(len(self.verts))
        vw, nw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "normal")
        cw, tw = GeomVertexWriter(vdata, "color"), GeomVertexWriter(vdata, "texcoord")
        for p, n, c, uv in self.verts:
            vw.addData3(p)
            nw.addData3(n)
            cw.addData4(c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0)
            tw.addData2(uv[0], uv[1])
        prim = GeomTriangles(Geom.UHStatic)
        for i in range(0, len(self.verts), 3):
            prim.addVertices(i, i + 1, i + 2)
        geom = Geom(vdata)
        geom.addPrimitive(prim)
        node = GeomNode(name)
        node.addGeom(geom)
        return NodePath(node)


_ICO_CACHE: dict = {}


def icosphere_data(subdiv: int):
    if subdiv in _ICO_CACHE:
        return _ICO_CACHE[subdiv]
    t = (1 + 5 ** 0.5) / 2
    verts = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
             (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    verts = [tuple(c / math.sqrt(sum(x * x for x in v)) for c in v) for v in verts]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
             (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5),
             (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(subdiv):
        cache: dict = {}
        new_faces = []

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                va, vb = verts[a], verts[b]
                m = [(va[i] + vb[i]) / 2 for i in range(3)]
                length = math.sqrt(sum(x * x for x in m))
                verts.append(tuple(x / length for x in m))
                cache[key] = len(verts) - 1
            return cache[key]

        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            new_faces += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = new_faces
    _ICO_CACHE[subdiv] = (list(verts), list(faces))
    return _ICO_CACHE[subdiv]


def uv_sphere(radius: float, rings: int = 48, segments: int = 96, name: str = "sphere") -> NodePath:
    """Esfera suave con UV equirectangulares (planetas y lunas)."""
    fmt = GeomVertexFormat.getV3n3t2()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vw, nw, tw = (GeomVertexWriter(vdata, c) for c in ("vertex", "normal", "texcoord"))
    for r in range(rings + 1):
        v = r / rings
        phi = math.pi * (v - 0.5)
        for s in range(segments + 1):
            u = s / segments
            theta = 2 * math.pi * u
            n = Vec3(math.cos(phi) * math.cos(theta), math.cos(phi) * math.sin(theta), math.sin(phi))
            vw.addData3(n * radius)
            nw.addData3(n)
            tw.addData2(u, v)
    prim = GeomTriangles(Geom.UHStatic)
    row = segments + 1
    for r in range(rings):
        for s in range(segments):
            a = r * row + s
            b = a + row
            prim.addVertices(a, a + 1, b + 1)
            prim.addVertices(a, b + 1, b)
    geom = Geom(vdata)
    geom.addPrimitive(prim)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


def annulus(r_inner: float, r_outer: float, segments: int = 128, name: str = "ring") -> NodePath:
    """Anillo plano en el plano XY con U radial (para los anillos planetarios)."""
    fmt = GeomVertexFormat.getV3n3t2()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vw, nw, tw = (GeomVertexWriter(vdata, c) for c in ("vertex", "normal", "texcoord"))
    for i in range(segments + 1):
        a = 2 * math.pi * i / segments
        for r, u in ((r_inner, 0.0), (r_outer, 1.0)):
            vw.addData3(math.cos(a) * r, math.sin(a) * r, 0)
            nw.addData3(0, 0, 1)
            tw.addData2(u, i / segments)
    prim = GeomTriangles(Geom.UHStatic)
    for i in range(segments):
        a = i * 2
        prim.addVertices(a, a + 1, a + 3)
        prim.addVertices(a, a + 3, a + 2)
    geom = Geom(vdata)
    geom.addPrimitive(prim)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


def disc(radius: float, segments: int = 64, name: str = "disc") -> NodePath:
    """Disco en el plano XZ (mira hacia -Y) con UV 0..1, para el portal."""
    fmt = GeomVertexFormat.getV3n3t2()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vw, nw, tw = (GeomVertexWriter(vdata, c) for c in ("vertex", "normal", "texcoord"))
    vw.addData3(0, 0, 0)
    nw.addData3(0, -1, 0)
    tw.addData2(0.5, 0.5)
    for i in range(segments + 1):
        a = 2 * math.pi * i / segments
        vw.addData3(math.cos(a) * radius, 0, math.sin(a) * radius)
        nw.addData3(0, -1, 0)
        tw.addData2(0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a))
    prim = GeomTriangles(Geom.UHStatic)
    for i in range(1, segments + 1):
        prim.addVertices(0, i, i + 1)
    geom = Geom(vdata)
    geom.addPrimitive(prim)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


def section(y: float, w: float, h: float, z: float = 0.0, sides: int = 8, flat: float = 0.0) -> list:
    """Sección transversal octogonal (o de ``sides`` lados) en el plano XZ a la altura ``y``."""
    pts = []
    for i in range(sides):
        a = 2 * math.pi * i / sides + math.pi / sides
        x = math.cos(a) * w
        zz = math.sin(a) * h
        if flat and zz < 0:
            zz *= (1 - flat)
        pts.append(Point3(x, y, z + zz))
    return pts
