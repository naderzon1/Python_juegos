"""Generador de imágenes procedural en Python puro (sin numpy ni Pillow).

Compone un paisaje por capas a partir de la interpretación del prompt:
cielo según la hora, sol o luna con resplandor, nubes o estrellas, la escena
(cordilleras, bosque, mar, dunas, ciudad o espacio) con perspectiva
atmosférica, efectos del ánimo (lluvia, niebla) y un etalonado final.
Todo sale de ruido fractal y de la semilla, así que cada prompt produce una
imagen distinta y reproducible. El PNG se escribe a mano con zlib.
"""

from __future__ import annotations

import math
import random
import struct
import zlib

from .temas import Interpretacion

Color = tuple[float, float, float]

# ---------------------------------------------------------------- paletas

CIELOS = {
    "amanecer": [(0.0, (38, 56, 112)), (0.5, (170, 120, 160)), (0.82, (248, 172, 146)), (1.0, (255, 216, 172))],
    "dia": [(0.0, (46, 104, 186)), (0.6, (112, 170, 226)), (1.0, (204, 228, 246))],
    "atardecer": [(0.0, (28, 22, 68)), (0.42, (128, 52, 108)), (0.74, (236, 104, 72)), (1.0, (255, 192, 104))],
    "noche": [(0.0, (3, 5, 18)), (0.6, (12, 20, 50)), (1.0, (32, 46, 90))],
}
ASTRO = {  # (color, altura relativa sobre el horizonte, radio relativo)
    "amanecer": ((255, 238, 204), 0.82, 0.055),
    "dia": ((255, 252, 238), 0.22, 0.045),
    "atardecer": ((255, 214, 140), 0.78, 0.07),
    "noche": ((236, 236, 224), 0.28, 0.04),
}
NEBLINA = {
    "amanecer": (236, 176, 166), "dia": (196, 218, 236),
    "atardecer": (222, 118, 104), "noche": (42, 54, 98),
}
LUZ_HORA = {  # multiplicador e intensidad por canal del color de las capas cercanas
    "amanecer": (0.62, (1.12, 0.9, 0.98)), "dia": (1.0, (1.0, 1.0, 1.0)),
    "atardecer": (0.42, (1.25, 0.82, 0.92)), "noche": (0.2, (0.75, 0.9, 1.35)),
}
BASE_ESCENA = {
    "montana": (66, 76, 92), "bosque": (30, 72, 46), "desierto": (218, 168, 104),
    "ciudad": (60, 68, 90), "mar": (28, 62, 84),
}
NEBULOSAS = {  # dos colores por ánimo para el espacio
    "alegre": ((236, 84, 160), (64, 210, 236)), "calma": ((40, 150, 170), (70, 90, 210)),
    "triste": ((60, 80, 150), (120, 130, 160)), "epico": ((230, 70, 40), (250, 170, 60)),
    "misterio": ((130, 50, 190), (40, 190, 140)),
}
ETALONADO = {  # saturación, tinte, contraste
    "alegre": (1.18, (1.04, 1.02, 0.98), 1.06), "calma": (0.92, (0.98, 1.0, 1.03), 0.96),
    "triste": (0.62, (0.94, 0.98, 1.08), 0.98), "epico": (1.12, (1.07, 1.0, 0.94), 1.14),
    "misterio": (0.85, (1.0, 0.95, 1.08), 1.04),
}


def _mezclar(a: Color, b: Color, t: float) -> Color:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _degradado(paradas, t: float) -> Color:
    for (t0, c0), (t1, c1) in zip(paradas, paradas[1:]):
        if t <= t1:
            return _mezclar(c0, c1, (t - t0) / (t1 - t0) if t1 > t0 else 0.0)
    return paradas[-1][1]


# ----------------------------------------------------------------- ruido

class Ruido2D:
    """Ruido de valor con interpolación suave y suma fractal de octavas."""

    def __init__(self, rng: random.Random, tam: int = 64):
        self.tam = tam
        self.v = [rng.random() for _ in range(tam * tam)]

    def valor(self, x: float, y: float) -> float:
        t = self.tam
        xi, yi = math.floor(x), math.floor(y)
        fx, fy = x - xi, y - yi
        fx = fx * fx * (3 - 2 * fx)
        fy = fy * fy * (3 - 2 * fy)
        x0, y0 = xi % t, yi % t
        x1, y1 = (x0 + 1) % t, (y0 + 1) % t
        v = self.v
        a = v[y0 * t + x0] + (v[y0 * t + x1] - v[y0 * t + x0]) * fx
        b = v[y1 * t + x0] + (v[y1 * t + x1] - v[y1 * t + x0]) * fx
        return a + (b - a) * fy

    def fractal(self, x: float, y: float, octavas: int = 4) -> float:
        total, amp, norm = 0.0, 1.0, 0.0
        for _ in range(octavas):
            total += self.valor(x, y) * amp
            norm += amp
            amp *= 0.5
            x, y = x * 2.03 + 17.1, y * 2.03 + 9.7
        return total / norm


def ruido1d(n: int, rng: random.Random, escala: float, octavas: int = 5,
            crestas: bool = False) -> list[float]:
    """Perfil 1D en [0, 1]; con `crestas` produce picos afilados de montaña."""
    salida = [0.0] * n
    amp, norm, frec = 1.0, 0.0, escala
    for _ in range(octavas):
        puntos = [rng.random() for _ in range(int(n * frec) + 3)]
        for x in range(n):
            p = x * frec
            i = int(p)
            f = p - i
            f = (1 - math.cos(f * math.pi)) * 0.5
            v = puntos[i] + (puntos[i + 1] - puntos[i]) * f
            if crestas:
                v = 1.0 - abs(v * 2 - 1)
            salida[x] += v * amp
        norm += amp
        amp *= 0.5
        frec *= 2.1
    return [v / norm for v in salida]


# ---------------------------------------------------------------- lienzo

class Lienzo:
    def __init__(self, ancho: int, alto: int):
        self.w, self.h = ancho, alto
        self.px = bytearray(ancho * alto * 3)

    def fila(self, y: int, c: Color) -> None:
        w = self.w
        self.px[y * w * 3:(y + 1) * w * 3] = bytes(_c8(c)) * w

    def mezclar(self, x: int, y: int, c: Color, a: float) -> None:
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        if a > 1:
            a = 1.0
        i = (y * self.w + x) * 3
        p = self.px
        p[i] = int(p[i] + (c[0] - p[i]) * a)
        p[i + 1] = int(p[i + 1] + (c[1] - p[i + 1]) * a)
        p[i + 2] = int(p[i + 2] + (c[2] - p[i + 2]) * a)

    def sumar(self, x: int, y: int, c: Color, a: float) -> None:
        """Mezcla aditiva (luz): resplandores, estrellas, nebulosas."""
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        i = (y * self.w + x) * 3
        p = self.px
        p[i] = min(255, int(p[i] + c[0] * a))
        p[i + 1] = min(255, int(p[i + 1] + c[1] * a))
        p[i + 2] = min(255, int(p[i + 2] + c[2] * a))

    def leer(self, x: int, y: int) -> tuple[int, int, int]:
        i = (y * self.w + x) * 3
        return self.px[i], self.px[i + 1], self.px[i + 2]

    def png(self) -> bytes:
        w, h, p = self.w, self.h, self.px
        crudo = b"".join(b"\x00" + bytes(p[y * w * 3:(y + 1) * w * 3]) for y in range(h))

        def bloque(tipo: bytes, datos: bytes) -> bytes:
            return (struct.pack(">I", len(datos)) + tipo + datos
                    + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF))

        return (b"\x89PNG\r\n\x1a\n"
                + bloque(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + bloque(b"IDAT", zlib.compress(crudo, 6))
                + bloque(b"IEND", b""))


def _c8(c: Color) -> tuple[int, int, int]:
    return tuple(0 if v < 0 else 255 if v > 255 else int(v) for v in c)


# ------------------------------------------------------------ elementos

def _cielo(lz: Lienzo, hora: str, horizonte: int) -> None:
    paradas = CIELOS[hora]
    for y in range(lz.h):
        lz.fila(y, _degradado(paradas, min(1.0, y / max(1, horizonte))))


def _estrellas(lz: Lienzo, rng: random.Random, hasta: int, cantidad: int) -> None:
    for _ in range(cantidad):
        x, y = rng.randrange(lz.w), rng.randrange(max(1, hasta))
        brillo = rng.random() ** 3
        tono = rng.choice([(255, 255, 255), (200, 220, 255), (255, 230, 200)])
        lz.sumar(x, y, tono, 0.35 + 0.65 * brillo)
        if brillo > 0.75:  # las más brillantes con destello en cruz
            for d in (1, 2):
                a = 0.5 / d
                for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d)):
                    lz.sumar(x + dx, y + dy, tono, a)


def _astro(lz: Lienzo, rng: random.Random, hora: str, horizonte: int,
           ruido: Ruido2D) -> tuple[int, int]:
    color, altura, radio_rel = ASTRO[hora]
    r = max(4, int(lz.h * radio_rel))
    cx = int(lz.w * rng.uniform(0.22, 0.78))
    cy = int(horizonte * altura)
    alcance = r * (5 if hora != "dia" else 4)
    luna = hora == "noche"
    disco = color if luna else _mezclar(color, (255, 255, 250), 0.65)
    for y in range(max(0, cy - alcance), min(lz.h, cy + alcance)):
        dy = y - cy
        for x in range(max(0, cx - alcance), min(lz.w, cx + alcance)):
            d = math.sqrt((x - cx) ** 2 + dy * dy)
            g = 1.0 - max(0.0, d - r) / (alcance - r)
            if g > 0:  # resplandor (también bajo el borde del disco)
                lz.sumar(x, y, color, g * g * (0.22 if luna else 0.5))
            if d < r + 1:
                c = disco
                if luna:  # cráteres suaves
                    n = ruido.fractal(x * 0.18, y * 0.18, 3)
                    c = _mezclar(color, (170, 172, 180), max(0.0, n - 0.45) * 1.6)
                lz.mezclar(x, y, c, min(1.0, r + 1 - d))  # borde con antialias
    return cx, cy


def _nubes(lz: Lienzo, rng: random.Random, ruido: Ruido2D, hora: str, horizonte: int,
           densidad: float) -> None:
    luz = {"amanecer": (255, 206, 190), "dia": (255, 255, 255),
           "atardecer": (255, 170, 120), "noche": (70, 80, 110)}[hora]
    sombra = _mezclar(CIELOS[hora][0][1], luz, 0.45)
    umbral = 0.62 - densidad * 0.18
    ox, oy = rng.uniform(0, 50), rng.uniform(0, 50)
    sx = 4.0 / lz.w
    for y in range(0, int(horizonte * 0.78)):
        # Las nubes se aplanan y aclaran cerca del horizonte (perspectiva).
        t = y / horizonte
        sy = 14.0 / lz.h * (1.0 + t * 1.8)
        for x in range(lz.w):
            n = ruido.fractal(x * sx + ox, y * sy + oy, 4)
            if n > umbral:
                a = min(1.0, (n - umbral) * 5.0) * (1.0 - t * 0.7)
                arriba = ruido.fractal(x * sx + ox, (y - 3) * sy + oy, 2)
                c = _mezclar(sombra, luz, min(1.0, 0.35 + (n - arriba) * 6 + 0.4))
                lz.mezclar(x, y, c, a * 0.9)


def _color_capa(escena: str, hora: str, profundidad: float) -> Color:
    """Color de una capa: oscura y saturada cerca, perdida en la neblina lejos."""
    mult, tinte = LUZ_HORA[hora]
    base = BASE_ESCENA[escena]
    cerca = (base[0] * mult * tinte[0], base[1] * mult * tinte[1], base[2] * mult * tinte[2])
    return _mezclar(cerca, NEBLINA[hora], profundidad ** 1.15 * 0.88)


def _relleno_perfil(lz: Lienzo, alturas: list[int], color: Color, neblina: Color,
                    espesor: float, sombreado: list[float] | None = None) -> None:
    """Rellena desde el perfil hacia abajo con neblina que se acumula al pie."""
    w, h, p = lz.w, lz.h, lz.px
    fondo = max(1.0, espesor)
    # La neblina se mide desde un perfil suavizado: si se midiera desde el borde
    # dentado, cada columna empezaría a otra altura y saldrían rayas verticales.
    ref = _suavizar([float(a) for a in alturas], max(4, w // 25))
    for x in range(w):
        y0 = max(0, alturas[x])
        r0 = ref[x]
        s = sombreado[x] if sombreado is not None else 0.0
        for y in range(y0, h):
            t = (y - r0) / fondo
            t = 0.0 if t < 0 else 1.0 if t > 1 else t
            # La sombra de la ladera se nota en la cresta y se diluye hacia abajo.
            k = 1 - s * 0.45 * (1 - t) ** 2
            f = t * 0.55
            r = color[0] * k + (neblina[0] - color[0] * k) * f
            g = color[1] * k + (neblina[1] - color[1] * k) * f
            b = color[2] * k + (neblina[2] - color[2] * k) * f
            i = (y * w + x) * 3
            p[i], p[i + 1], p[i + 2] = int(r), int(g), int(b)
        if 0 < y0 < h:  # borde suave
            lz.mezclar(x, y0 - 1, color, 0.5)


def _montanas(lz, rng, hora, horizonte, capas=4):
    for k in range(capas):
        prof = (1.0 - k / (capas - 1)) * 0.82  # 0.82 = lejos
        perfil = ruido1d(lz.w, rng, escala=0.006 + 0.004 * k, octavas=6, crestas=True)
        base = horizonte + int(lz.h * (0.02 + 0.09 * k))
        amp = lz.h * (0.42 - 0.07 * k)
        alturas = [int(base - v * amp) for v in perfil]
        color = _color_capa("montana", hora, prof)
        # Ladera iluminada a un lado y en sombra al otro según la pendiente.
        suave = _suavizar(perfil, 5)
        somb = [min(1.0, max(0.0, (suave[min(lz.w - 1, x + 3)] - suave[max(0, x - 3)]) * 14 + 0.45))
                for x in range(lz.w)]
        somb = _suavizar(somb, 2)
        _relleno_perfil(lz, alturas, color, NEBLINA[hora], lz.h * 0.16, somb)
        if k == 0 and hora in ("dia", "amanecer"):  # nieve en las cumbres lejanas
            cima = min(alturas)
            limite = cima + amp * 0.2
            for x in range(lz.w):
                for y in range(alturas[x], min(lz.h, int(limite))):
                    borde = min(1.0, (limite - y) / (amp * 0.05))
                    lz.mezclar(x, y, (246, 248, 255), 0.7 * borde * (1 - somb[x] * 0.55))


def _suavizar(valores: list[float], radio: int) -> list[float]:
    n, salida = len(valores), []
    acum = [0.0]
    for v in valores:
        acum.append(acum[-1] + v)
    for i in range(n):
        a, b = max(0, i - radio), min(n, i + radio + 1)
        salida.append((acum[b] - acum[a]) / (b - a))
    return salida


def _bruma(lz: Lienzo, color: Color, desde: int, hasta: int, maximo: float) -> None:
    """Banda de neblina que crece hacia abajo entre `desde` y `hasta`."""
    w, p = lz.w, lz.px
    for y in range(max(0, desde), lz.h):
        a = maximo * min(1.0, (y - desde) / max(1, hasta - desde))
        if a <= 0:
            continue
        for x in range(w):
            i = (y * w + x) * 3
            p[i] = int(p[i] + (color[0] - p[i]) * a)
            p[i + 1] = int(p[i + 1] + (color[1] - p[i + 1]) * a)
            p[i + 2] = int(p[i + 2] + (color[2] - p[i + 2]) * a)


def _pino(lz: Lienzo, x0: int, base: int, alto: int, color: Color) -> None:
    ancho = alto * 0.42
    pisos = 4
    for y in range(max(0, base - alto), min(lz.h, base)):
        t = (y - (base - alto)) / alto
        piso = (t * pisos) % 1.0
        medio = ancho * 0.5 * (0.25 + 0.75 * t) * (0.55 + 0.45 * piso)
        for x in range(int(x0 - medio), int(x0 + medio) + 1):
            lz.mezclar(x, y, color, 1.0)
    for y in range(base, min(lz.h, base + max(2, alto // 10))):  # tronco
        for x in range(x0 - max(1, alto // 30), x0 + max(1, alto // 30) + 1):
            lz.mezclar(x, y, color, 1.0)


def _bosque(lz, rng, hora, horizonte):
    for k in range(2):  # colinas de fondo
        perfil = ruido1d(lz.w, rng, 0.004, 4)
        alturas = [int(horizonte + lz.h * 0.02 * k - v * lz.h * (0.2 - 0.06 * k)) for v in perfil]
        _relleno_perfil(lz, alturas, _color_capa("bosque", hora, 0.95 - 0.2 * k), NEBLINA[hora], lz.h * 0.2)
    for k in range(4):  # hileras de pinos de lejos a cerca
        prof = 0.75 - k * 0.25
        color = _color_capa("bosque", hora, max(0.0, prof))
        suelo = horizonte + int(lz.h * (0.06 + 0.1 * k))
        perfil = ruido1d(lz.w, rng, 0.01, 3)
        alturas = [int(suelo - v * lz.h * 0.04) for v in perfil]
        _relleno_perfil(lz, alturas, color, NEBLINA[hora], lz.h * 0.25)
        tam = lz.h * (0.1 + 0.09 * k)
        x = rng.uniform(-10, 0)
        while x < lz.w + 10:
            xi = int(x)
            alto = int(tam * rng.uniform(0.7, 1.3))
            _pino(lz, xi, alturas[min(lz.w - 1, max(0, xi))] + 2, alto, color)
            x += tam * rng.uniform(0.12, 0.3)
        if k < 3:
            _bruma(lz, NEBLINA[hora], int(suelo - tam * 0.7), int(suelo + lz.h * 0.04), 0.5 - 0.1 * k)


def _mar(lz, rng, hora, horizonte, sol):
    w, h = lz.w, lz.h
    if rng.random() < 0.7:  # islas o costa lejana
        perfil = ruido1d(w, rng, 0.008, 5)
        corte = rng.uniform(0.45, 0.6)
        alturas = [int(horizonte - max(0.0, v - corte) * h * 0.5) if v > corte else h + 1 for v in perfil]
        color = _color_capa("montana", hora, 0.7)
        for x in range(w):
            for y in range(max(0, alturas[x]), horizonte):
                lz.mezclar(x, y, color, 1.0)
    agua = _color_capa("mar", hora, 0.2)
    sx, _sy = sol
    color_sol = ASTRO[hora][0]
    fase = rng.uniform(0, 6.28)
    for y in range(horizonte, h):
        prof = (y - horizonte) / max(1, h - horizonte)  # 0 en el horizonte
        espejo = max(0, 2 * horizonte - y - 1)
        ancho_brillo = w * (0.02 + 0.16 * prof)
        for x in range(w):
            ola = math.sin(x * 0.045 / (0.3 + prof) + y * 0.9 + fase) * math.sin(y * 0.37 + x * 0.011)
            ex = min(w - 1, max(0, x + int(ola * 4 * (0.3 + prof))))
            r, g, b = lz.leer(ex, min(espejo, h - 1))
            refl = 0.75 - prof * 0.45
            c = (r * refl + agua[0] * (1 - refl), g * refl + agua[1] * (1 - refl),
                 b * refl + agua[2] * (1 - refl))
            c = _mezclar(c, (c[0] * 0.8, c[1] * 0.8, c[2] * 0.85), prof * 0.6)
            i = (y * w + x) * 3
            lz.px[i], lz.px[i + 1], lz.px[i + 2] = _c8(c)
            dx = abs(x - sx)
            if dx < ancho_brillo and ola > 0.25:  # camino de luz del sol o la luna
                lz.sumar(x, y, color_sol, (1 - dx / ancho_brillo) * (ola - 0.25) * 1.3)
        if y == horizonte:
            for x in range(w):
                lz.mezclar(x, y, NEBLINA[hora], 0.5)


def _desierto(lz, rng, hora, horizonte):
    for k in range(4):
        prof = 1.0 - k / 3
        fases = [rng.uniform(0, 6.28) for _ in range(3)]
        frec = [rng.uniform(0.004, 0.008), rng.uniform(0.01, 0.02), rng.uniform(0.025, 0.04)]
        amp = lz.h * (0.05 + 0.03 * k)
        base = horizonte + int(lz.h * (0.02 + 0.1 * k))
        perfil, pend = [], []
        for x in range(lz.w):
            v = sum(math.sin(x * f + p) / (i + 1) ** 1.3 for i, (f, p) in enumerate(zip(frec, fases)))
            d = sum(math.cos(x * f + p) * f / (i + 1) ** 1.3 for i, (f, p) in enumerate(zip(frec, fases)))
            perfil.append(int(base - v * amp))
            pend.append(d)
        maxp = max(abs(d) for d in pend) or 1
        somb = [min(1.0, max(0.0, 0.5 + d / maxp * 0.7)) for d in pend]
        _relleno_perfil(lz, perfil, _color_capa("desierto", hora, prof * 0.85), NEBLINA[hora],
                        lz.h * 0.3, somb)


def _edificios(lz, rng, hora, suelo, alto_max, color, ventanas):
    x = rng.randint(-20, 0)
    luz = (255, 214, 130) if hora in ("noche", "atardecer") else (150, 190, 220)
    prob = {"noche": 0.45, "atardecer": 0.25, "amanecer": 0.15, "dia": 0.5}[hora]
    while x < lz.w:
        ancho = rng.randint(int(lz.w * 0.03), int(lz.w * 0.09))
        alto = int(alto_max * rng.uniform(0.35, 1.0))
        tope = suelo - alto
        for y in range(max(0, tope), min(lz.h, suelo + 1)):
            for xx in range(max(0, x), min(lz.w, x + ancho)):
                lz.mezclar(xx, y, color, 1.0)
        if rng.random() < 0.3:  # antena o remate
            for y in range(max(0, tope - alto // 6), tope):
                lz.mezclar(x + ancho // 2, y, color, 1.0)
        if ventanas:
            paso = max(4, ancho // 6)
            for wy in range(tope + 4, suelo - 3, paso):
                for wx in range(x + 3, x + ancho - 3, paso):
                    if rng.random() < prob:
                        a = rng.uniform(0.5, 1.0) * (0.55 if hora == "dia" else 1.0)
                        for dy in range(max(1, paso // 2)):
                            for dx in range(max(1, paso // 2)):
                                lz.mezclar(wx + dx, wy + dy, luz, a)
        x += ancho + rng.randint(0, 4)


def _ciudad(lz, rng, hora, horizonte):
    for k in range(3):
        prof = 1.0 - k / 2
        color = _color_capa("ciudad", hora, prof * 0.8)
        suelo = horizonte + int(lz.h * (0.05 + 0.12 * k))
        _edificios(lz, rng, hora, suelo, lz.h * (0.28 + 0.12 * k), color, ventanas=k > 0)
    calle = _color_capa("ciudad", hora, 0.0)
    for y in range(int(horizonte + lz.h * 0.29), lz.h):
        for x in range(lz.w):
            lz.mezclar(x, y, calle, 1.0)


def _espacio(lz, rng, ruido, animo):
    w, h = lz.w, lz.h
    c1, c2 = NEBULOSAS[animo]
    ox, oy = rng.uniform(0, 40), rng.uniform(0, 40)
    ang = rng.uniform(-0.6, 0.6)
    ca, sa = math.cos(ang), math.sin(ang)
    sx, sy = 3.0 / w, 3.0 / w
    for y in range(h):
        for x in range(w):
            # Banda diagonal (como la Vía Láctea) modulada por ruido fractal.
            u = (x - w / 2) * ca + (y - h / 2) * sa
            v = -(x - w / 2) * sa + (y - h / 2) * ca
            banda = math.exp(-(v / (h * 0.32)) ** 2)
            n = ruido.fractal(u * sx + ox, v * sy * 2 + oy, 5)
            m = ruido.fractal(u * sx * 2 + oy, v * sy * 2 + ox, 3)
            a = max(0.0, n - 0.35) * 1.9 * banda
            if a > 0:
                lz.sumar(x, y, _mezclar(c1, c2, m), a * 0.85)
                if n > 0.62:
                    lz.sumar(x, y, (255, 240, 230), (n - 0.62) * 1.4 * banda)
    _estrellas(lz, rng, h, int(w * h / 90))
    # Planeta con sombreado, bandas y atmósfera.
    r = int(h * rng.uniform(0.16, 0.26))
    cx = int(w * rng.choice([0.2, 0.78])) + rng.randint(-20, 20)
    cy = int(h * rng.uniform(0.55, 0.75))
    base = _mezclar(c2, (200, 190, 170), 0.4)
    lx, ly = (-0.6, -0.5) if cx > w / 2 else (0.6, -0.5)
    anillo = rng.random() < 0.55
    for y in range(max(0, cy - r - 4), min(h, cy + r + 5)):
        for x in range(max(0, cx - r - 4), min(w, cx + r + 5)):
            dx, dy = (x - cx) / r, (y - cy) / r
            d2 = dx * dx + dy * dy
            if d2 <= 1.0:
                nz = math.sqrt(1 - d2)
                luz = max(0.0, dx * lx + dy * ly + nz * 0.6)
                banda = ruido.fractal(dx * 1.5 + 3, dy * 9 + 5, 3)
                c = _mezclar(base, _mezclar(c1, (40, 30, 30), 0.4), banda)
                c = (c[0] * (0.06 + luz), c[1] * (0.06 + luz), c[2] * (0.08 + luz))
                lz.mezclar(x, y, c, min(1.0, (1 - math.sqrt(d2)) * r))
            elif d2 < 1.12:
                atm = (1.12 - d2) / 0.12
                lz.sumar(x, y, c2, atm * atm * 0.55 * max(0.2, (dx * lx + dy * ly) + 0.5))
    if anillo:
        inc = rng.uniform(0.18, 0.3)
        for y in range(max(0, cy - r), min(h, cy + r)):
            for x in range(max(0, cx - int(r * 2.3)), min(w, cx + int(r * 2.3))):
                dx, dy = (x - cx) / r, (y - cy) / (r * inc)
                d = math.sqrt(dx * dx + dy * dy)
                if 1.35 < d < 2.2:
                    delante = dy > 0 or (dx * dx + ((y - cy) / r) ** 2) > 1
                    if delante:
                        a = (0.35 + 0.35 * math.sin(d * 23)) * (1 - abs(d - 1.77) / 0.43)
                        lz.mezclar(x, y, _mezclar(base, (230, 220, 200), 0.5), a * 0.8)


def _lluvia(lz: Lienzo, rng: random.Random, cantidad: int) -> None:
    for _ in range(cantidad):
        x, y = rng.randrange(lz.w), rng.randrange(lz.h)
        largo = rng.randint(6, 16)
        for k in range(largo):
            lz.mezclar(x - k // 4, y + k, (200, 210, 230), 0.22 * (1 - k / largo))


def _niebla(lz: Lienzo, rng: random.Random, ruido: Ruido2D, color: Color, desde: int) -> None:
    ox = rng.uniform(0, 30)
    for y in range(desde, lz.h):
        t = (y - desde) / max(1, lz.h - desde)
        for x in range(lz.w):
            n = ruido.fractal(x * 3.0 / lz.w + ox, y * 9.0 / lz.h, 3)
            lz.mezclar(x, y, color, max(0.0, n - 0.3) * (0.3 + 0.5 * math.sin(t * math.pi)))


def _etalonar(lz: Lienzo, rng: random.Random, animo: str) -> None:
    """Etalonado por ánimo, viñeta y grano fino en una sola pasada."""
    sat, tinte, contraste = ETALONADO[animo]
    w, h, p = lz.w, lz.h, lz.px
    curva = [0] * 256
    for v in range(256):
        c = (v / 255 - 0.5) * contraste + 0.5
        curva[v] = c
    grano = [rng.uniform(-4, 4) for _ in range(997)]
    vx = [1 - 0.35 * ((x / w - 0.5) * 2) ** 2 for x in range(w)]
    gi = 0
    for y in range(h):
        vy = 1 - 0.3 * ((y / h - 0.5) * 2) ** 2
        for x in range(w):
            i = (y * w + x) * 3
            r, g, b = p[i], p[i + 1], p[i + 2]
            lum = r * 0.3 + g * 0.59 + b * 0.11
            v = vx[x] * vy
            gi = (gi + 1) % 997
            n = grano[gi]
            out = []
            for canal, t in ((r, tinte[0]), (g, tinte[1]), (b, tinte[2])):
                c = (lum + (canal - lum) * sat) * t
                c = curva[0 if c < 0 else 255 if c > 255 else int(c)] * 255 * v + n
                out.append(0 if c < 0 else 255 if c > 255 else int(c))
            p[i], p[i + 1], p[i + 2] = out


# --------------------------------------------------------------- público

def generar_imagen(interp: Interpretacion, ancho: int = 512, alto: int = 320) -> bytes:
    """Devuelve los bytes de un PNG que ilustra el prompt."""
    rng = random.Random(interp.semilla ^ 0x1A6E)
    ruido = Ruido2D(rng)
    lz = Lienzo(ancho, alto)
    escena, hora, animo = interp.escena, interp.hora, interp.animo

    if escena == "espacio":
        lz.px[:] = bytes((4, 5, 14)) * (ancho * alto)
        _espacio(lz, rng, ruido, animo)
    else:
        horizonte = int(alto * {"mar": 0.56, "desierto": 0.58, "ciudad": 0.5}.get(escena, 0.55))
        _cielo(lz, hora, horizonte)
        if hora == "noche":
            _estrellas(lz, rng, horizonte, int(ancho * horizonte / 120))
        sol = _astro(lz, rng, hora, horizonte, ruido)
        if hora != "noche" or animo in ("triste", "misterio"):
            dens = {"triste": 1.0, "misterio": 0.8, "epico": 0.7}.get(animo, 0.35)
            _nubes(lz, rng, ruido, hora, horizonte, dens)
        {"montana": lambda: _montanas(lz, rng, hora, horizonte),
         "bosque": lambda: _bosque(lz, rng, hora, horizonte),
         "mar": lambda: _mar(lz, rng, hora, horizonte, sol),
         "desierto": lambda: _desierto(lz, rng, hora, horizonte),
         "ciudad": lambda: _ciudad(lz, rng, hora, horizonte)}[escena]()
        if animo == "misterio":
            _niebla(lz, rng, ruido, NEBLINA[hora], int(horizonte * 0.7))
        if animo == "triste":
            _lluvia(lz, rng, int(ancho * alto / 260))
    _etalonar(lz, rng, animo)
    return lz.png()
