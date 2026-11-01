"""Plan semántico: el mismo JSON que pedía la página a Claude, deducido sin red."""

from __future__ import annotations

import colorsys
import random

from . import lexico as lx
from .temas import OBJETOS, TEMAS

VERBO = {"explicar": "Explicar", "poema": "Escribir un poema sobre", "cancion": "Cantar una canción para",
         "cuento": "Contar una historia sobre", "escena": "Describir"}
CARACTERES = ["calmo", "ondulante", "pulsante", "solemne"]


def _hex_a_rgb(h: str) -> tuple[float, float, float]:
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]


def _rgb_a_hex(r: float, g: float, b: float) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in (r, g, b))


def mezclar(a: str, b: str, t: float) -> str:
    ra, rb = _hex_a_rgb(a), _hex_a_rgb(b)
    return _rgb_a_hex(*(x + (y - x) * t for x, y in zip(ra, rb)))


def girar(h: str, grados: float) -> str:
    hh, ll, ss = colorsys.rgb_to_hls(*_hex_a_rgb(h))
    return _rgb_a_hex(*colorsys.hls_to_rgb((hh + grados / 360) % 1, ll, ss))


def luminancia(h: str) -> float:
    r, g, b = _hex_a_rgb(h)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def paleta(temas: list[str], rnd: random.Random) -> list[str]:
    base = list(lx.tema(temas[0] if temas else "").get("paleta"))
    if len(temas) > 1:  # el segundo tema tiñe los tonos medios
        otra = TEMAS[temas[1]]["paleta"]
        base[2] = mezclar(base[2], otra[2], 0.45)
        base[3] = mezclar(base[3], otra[3], 0.35)
    giro = rnd.uniform(-10, 10)
    return sorted((girar(c, giro) for c in base), key=luminancia)


def titulo(tema_txt: str) -> str:
    ws = tema_txt.split()
    while ws and ws[0].lower() in ("un", "una", "unos", "unas"):
        ws = ws[1:]
    ws = ws[:6]
    while len(ws) > 1 and ws[-1].lower() in lx.STOP:
        ws = ws[:-1]
    return lx.mayuscula(" ".join(ws)) or "Prisma"


def escena(temas: list[str], objetos: list[str], tema_txt: str) -> str:
    partes = []
    if "faro" in objetos:
        partes.append("un faro sobre las rocas que lanza su haz de luz")
    if "barco" in objetos:
        partes.append("un barco pequeño sobre el agua")
    if "robot" in objetos and "robot" not in temas:
        partes.append(TEMAS["robot"]["visual"])
    for n in temas[:3]:
        partes.append(TEMAS[n]["visual"])
    if not partes:
        partes.append(lx.tema("")["visual"])
    frase = partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]
    return lx.mayuscula(frase) + f"; la imagen evoca «{tema_txt}»."


def generar(texto: str, semilla: int = 0) -> dict:
    rnd = random.Random(semilla)
    tema_txt = lx.tema_principal(texto)
    objetos = lx.objetos_detectados(texto)
    temas = lx.temas_detectados(texto)
    for obj in objetos:  # el faro trae el mar, el barco también
        acompana = OBJETOS[obj][1]
        if acompana and acompana not in temas:
            temas.append(acompana)
    principal = lx.tema(temas[0] if temas else "")
    pol = lx.polaridad(texto) or principal["polaridad"]

    escala = principal["escala"]
    if pol < 0 and escala in ("mayor", "lidia"):
        escala = "menor"
    elif pol > 0 and escala in ("menor", "frigia"):
        escala = "dorica"
    exclamaciones = sum(texto.count(c) for c in "!¡")
    tempo = principal["tempo"] + exclamaciones * 6 + rnd.randint(-6, 6)
    caracter = principal["caracter"] if rnd.random() < 0.8 else rnd.choice(CARACTERES)

    tono = principal["tono"]
    if len(temas) > 1 and TEMAS[temas[1]]["tono"] != tono:
        tono = f"{tono} y {TEMAS[temas[1]]['tono']}"

    modo = lx.intencion(texto)
    clave = lx.contenido(tema_txt)[:6] or lx.contenido(texto)[:6] or temas[:3]
    return {
        "titulo": titulo(tema_txt),
        "idioma": "es-ES",  # la IA local escribe en español
        "intencion": lx.contraer(f"{VERBO[modo]} {tema_txt}"),
        "tono": tono,
        "palabras_clave": clave,
        "paleta": paleta(temas, rnd),
        "musica": {"escala": escala, "tonica": rnd.choice("CDEFGAB"), "tempo": max(56, min(140, tempo)), "caracter": caracter},
        "escena": escena(temas, objetos, tema_txt),
        # datos extra para las otras etapas (la página ignora claves que no conoce)
        "temas": temas,
        "objetos": objetos,
        "modo": modo,
    }
