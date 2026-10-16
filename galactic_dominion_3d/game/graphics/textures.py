"""Texturas procedurales generadas con NumPy (planetas, nebulosas, paneles...).

No hay texturas externas en el proyecto: todo se genera al cargar una
galaxia a partir de su paleta, con semillas fijas para que cada galaxia
tenga siempre el mismo aspecto.
"""
from __future__ import annotations

import numpy as np
from panda3d.core import SamplerState, Texture


def value_noise(w: int, h: int, gx: int, gy: int, rng: np.random.Generator, tile_x: bool = True) -> np.ndarray:
    grid = rng.random((gy + 1, gx + 1))
    if tile_x:
        grid[:, -1] = grid[:, 0]
    xs = np.linspace(0, gx, w, endpoint=False)
    ys = np.linspace(0, gy, h, endpoint=False)
    x0, y0 = xs.astype(int), ys.astype(int)
    fx, fy = xs - x0, ys - y0
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    g00 = grid[np.ix_(y0, x0)]
    g10 = grid[np.ix_(y0, x0 + 1)]
    g01 = grid[np.ix_(y0 + 1, x0)]
    g11 = grid[np.ix_(y0 + 1, x0 + 1)]
    top = g00 * (1 - sx) + g10 * sx
    bottom = g01 * (1 - sx) + g11 * sx
    return top * (1 - sy[:, None]) + bottom * sy[:, None]


def fbm(w: int, h: int, rng: np.random.Generator, octaves: int = 6, base: int = 4, tile_x: bool = True,
        aspect: float = 0.5) -> np.ndarray:
    total = np.zeros((h, w))
    amp, norm = 1.0, 0.0
    for octave in range(octaves):
        freq = base * 2 ** octave
        total += value_noise(w, h, freq, max(1, int(freq * aspect)), rng, tile_x) * amp
        norm += amp
        amp *= 0.5
    return total / norm


def gradient(values: np.ndarray, palette: list) -> np.ndarray:
    """Colorea un mapa [0,1] interpolando entre los colores de la paleta."""
    pal = np.array(palette, dtype=float)
    pos = np.clip(values, 0, 1) * (len(pal) - 1)
    i0 = np.floor(pos).astype(int)
    i1 = np.minimum(i0 + 1, len(pal) - 1)
    t = (pos - i0)[..., None]
    return pal[i0] * (1 - t) + pal[i1] * t


def make_texture(rgb: np.ndarray, name: str, alpha: np.ndarray | None = None, wrap_u: bool = False,
                 mipmap: bool = True, wrap_v: bool = False) -> Texture:
    h, w = rgb.shape[:2]
    rgb8 = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    if alpha is not None:
        a8 = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
        data = np.dstack([rgb8, a8])
        fmt, comp = Texture.F_rgba, "RGBA"
    else:
        data = rgb8
        fmt, comp = Texture.F_rgb, "RGB"
    data = np.ascontiguousarray(data[::-1])  # Panda espera la fila inferior primero
    tex = Texture(name)
    tex.setup2dTexture(w, h, Texture.T_unsigned_byte, fmt)
    tex.setRamImageAs(data.tobytes(), comp)
    tex.setWrapU(SamplerState.WM_repeat if wrap_u else SamplerState.WM_clamp)
    tex.setWrapV(SamplerState.WM_repeat if wrap_v else SamplerState.WM_clamp)
    tex.setMagfilter(SamplerState.FT_linear)
    tex.setMinfilter(SamplerState.FT_linear_mipmap_linear if mipmap else SamplerState.FT_linear)
    tex.setAnisotropicDegree(4)
    return tex


# --- planetas ----------------------------------------------------------------
def planet_texture(kind: str, palette: list, size: int, seed: int) -> Texture:
    rng = np.random.default_rng(seed)
    w, h = size, size // 2
    lat = np.linspace(-1, 1, h)[:, None] * np.ones((1, w))
    n = fbm(w, h, rng, octaves=7, base=4)
    if kind == "gas":
        warp = fbm(w, h, rng, octaves=4, base=3)
        bands = 0.5 + 0.5 * np.sin(lat * 14 + warp * 5.5 + n * 2.0)
        storms = np.clip((fbm(w, h, rng, octaves=3, base=6) - 0.62) * 6, 0, 1)
        color = gradient(bands * 0.85 + n * 0.15, palette)
        color = color * (1 - storms[..., None] * 0.35) + np.array(palette[-1]) * storms[..., None] * 0.35
    elif kind == "lava":
        ridge = 1 - np.abs(2 * fbm(w, h, rng, octaves=6, base=5) - 1)
        cracks = np.clip((ridge - 0.86) * 9, 0, 1)
        color = gradient(n * 0.9, palette[:2])
        color = color * (1 - cracks[..., None]) + np.array(palette[2]) * cracks[..., None] * 1.3
    elif kind == "ice":
        ridge = 1 - np.abs(2 * fbm(w, h, rng, octaves=6, base=6) - 1)
        color = gradient(n, palette)
        color *= (1 - np.clip((ridge - 0.9) * 6, 0, 0.45))[..., None]
    else:  # rocoso
        continents = np.clip((n - 0.47) * 3.0 + 0.5, 0, 1)
        color = gradient(continents, palette)
        detail = fbm(w, h, rng, octaves=5, base=16)
        color *= (0.82 + detail * 0.3)[..., None]
        caps = np.clip((np.abs(lat) - 0.8) * 6, 0, 1)
        color = color * (1 - caps[..., None]) + np.array([0.92, 0.94, 0.97]) * caps[..., None]
    return make_texture(color, f"planet-{kind}-{seed}", wrap_u=True)


def ring_texture(palette: list, seed: int) -> Texture:
    rng = np.random.default_rng(seed)
    w = 512
    r = np.linspace(0, 1, w)
    bands = value_noise(w, 1, 60, 1, rng, tile_x=False)[0] * 0.6 + value_noise(w, 1, 200, 1, rng, False)[0] * 0.4
    alpha = np.clip(bands * 1.4 - 0.25, 0, 1) * np.clip(np.sin(r * np.pi) * 1.6, 0, 1)
    gaps = (np.abs(r - 0.62) < 0.015) | (np.abs(r - 0.33) < 0.008)
    alpha[gaps] *= 0.1
    color = gradient(bands, palette)
    rgb = np.repeat(color[None, :, :], 4, axis=0)
    return make_texture(rgb, f"ring-{seed}", alpha=np.repeat(alpha[None, :], 4, axis=0))


# --- sprites -----------------------------------------------------------------
def glow_texture(size: int = 64, power: float = 2.2) -> Texture:
    y, x = np.mgrid[-1:1:size * 1j, -1:1:size * 1j]
    d = np.sqrt(x * x + y * y)
    a = np.clip(1 - d, 0, 1) ** power
    return make_texture(np.ones((size, size, 3)), f"glow-{power}", alpha=a)


def ring_sprite(size: int = 128) -> Texture:
    y, x = np.mgrid[-1:1:size * 1j, -1:1:size * 1j]
    d = np.sqrt(x * x + y * y)
    a = np.exp(-((d - 0.82) ** 2) / 0.004) + np.exp(-((d - 0.8) ** 2) / 0.03) * 0.35
    return make_texture(np.ones((size, size, 3)), "ring-sprite", alpha=np.clip(a, 0, 1))


def cloud_texture(seed: int, size: int = 256) -> Texture:
    rng = np.random.default_rng(seed)
    n = fbm(size, size, rng, octaves=6, base=3, tile_x=False, aspect=1.0)
    y, x = np.mgrid[-1:1:size * 1j, -1:1:size * 1j]
    falloff = np.clip(1 - np.sqrt(x * x + y * y), 0, 1) ** 1.4
    alpha = np.clip((n - 0.32) * 1.9, 0, 1) * falloff
    tone = 0.75 + 0.25 * n
    return make_texture(np.dstack([tone, tone, tone]), f"cloud-{seed}", alpha=alpha)


def panel_texture(seed: int, size: int = 256) -> Texture:
    """Paneles metálicos con juntas y remaches para modular el color del casco."""
    rng = np.random.default_rng(seed)
    img = np.full((size, size), 0.9)
    # subdivisiones de paneles con tonos ligeramente distintos
    cells = [(0, 0, size, size)]
    for _ in range(5):
        nxt = []
        for x0, y0, x1, y1 in cells:
            if (x1 - x0) > 24 and rng.random() < 0.85:
                if (x1 - x0) >= (y1 - y0):
                    cut = int(rng.integers(x0 + 8, x1 - 8))
                    nxt += [(x0, y0, cut, y1), (cut, y0, x1, y1)]
                else:
                    cut = int(rng.integers(y0 + 8, y1 - 8))
                    nxt += [(x0, y0, x1, cut), (x0, cut, x1, y1)]
            else:
                nxt.append((x0, y0, x1, y1))
        cells = nxt
    for x0, y0, x1, y1 in cells:
        img[y0:y1, x0:x1] = 0.84 + rng.random() * 0.14
        img[y0:y1, x0] = 0.55
        img[y0, x0:x1] = 0.55
        if x1 - x0 > 30 and y1 - y0 > 30 and rng.random() < 0.4:
            for rx in (x0 + 4, x1 - 5):
                for ry in (y0 + 4, y1 - 5):
                    img[ry, rx] = 0.62
    grain = fbm(size, size, rng, octaves=4, base=16, tile_x=True, aspect=1.0)
    img = img * (0.93 + grain * 0.1)
    return make_texture(np.dstack([img, img, img]), f"panels-{seed}", wrap_u=True, wrap_v=True)
