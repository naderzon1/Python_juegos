"""Herramientas de lenguaje de la IA local: palabras, género, tema principal, intención y temas."""

from __future__ import annotations

import re
import unicodedata

from .temas import GENERAL, OBJETOS, TEMAS

STOP = set(
    "el la los las un una unos unas de del al a en y e o u que por para con sin sobre como mas más pero se su sus "
    "lo le les me mi mis tu tus te es son ser fue era muy ya este esta estos estas ese esa eso esto hay sea "
    "qué cómo cuál cuáles quién dónde cuándo porque cada entre hasta desde también tan todo toda todos todas "
    "the an of to in and or is are for with on at by it this that be as from".split()
)
# Verbos y nombres de la petición: dicen qué hacer, no de qué tratar
PETICION = set(
    "escribe escríbeme escribir crea créame crear haz hazme hacer dame genera generar quiero necesito puedes podrías "
    "explica explícame explicar cuéntame cuenta describe describir dibuja dibujar háblame habla dime define "
    "poema poesía canción cuento historia relato verso versos letra nana texto corto corta breve bonito bonita".split()
)

POSITIVO = re.compile(r"(amor|alegr|luz|sol|feliz|paz|sueñ|suen|esperanza|brill|calma|dulce|bonit|herm|vida|fiesta|amanecer|jard|flor|celebr|risa|libre)")
NEGATIVO = re.compile(r"(tormenta|oscur|miedo|triste|muerte|guerra|dolor|sombra|noche|frío|frio|soledad|llanto|caos|ruina|rabia|ira)")

# Raíces que solo cuentan como palabra completa (evita "amarillo" → amor)
EXACTAS = {"amar"}

FEMENINO_EXCEPCIONES = {"día", "dia", "mapa", "problema", "planeta", "sistema", "idioma", "tema", "poema", "clima", "programa", "sofá", "cometa"}


def sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def palabras(texto: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", texto.lower())


def contenido(texto: str) -> list[str]:
    """Palabras con significado propio, en orden y sin repetir."""
    vistas, salida = set(), []
    for p in palabras(texto):
        if p in STOP or p in PETICION or len(p) < 3 or p in vistas:
            continue
        vistas.add(p)
        salida.append(p)
    return salida


def polaridad(texto: str) -> int:
    toks = palabras(texto)
    pos = sum(1 for t in toks if POSITIVO.search(t))
    neg = sum(1 for t in toks if NEGATIVO.search(t))
    return 0 if pos == neg else (1 if pos > neg else -1)


def genero(palabra: str, texto: str = "") -> str:
    """'f' o 'm': primero por el artículo que la acompaña en el texto, luego por la terminación."""
    bajo = texto.lower()
    p = re.escape(palabra.lower())
    if re.search(rf"\b(una|la|esta|esa|las|unas|nuestra|mi)\s+(?:\w+\s+)?{p}\b", bajo):
        return "f"
    if re.search(rf"\b(un|el|este|ese|los|unos|del|al|nuestro)\s+(?:\w+\s+)?{p}\b", bajo):
        return "m"
    w = palabra.lower()
    if w in FEMENINO_EXCEPCIONES:
        return "m"
    if w.endswith(("a", "ión", "ion", "dad", "tad", "tud", "umbre", "ez")):
        return "f"
    return "m"


def con_articulo(sust: str, g: str, definido: bool = True) -> str:
    if definido:
        return ("la " if g == "f" else "el ") + sust
    return ("una " if g == "f" else "un ") + sust


def contraer(s: str) -> str:
    s = re.sub(r"\bde el\b", "del", s)
    return re.sub(r"\ba el\b", "al", s)


def mayuscula(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def intencion(texto: str) -> str:
    """explicar | poema | cancion | cuento | escena"""
    t = sin_tildes(texto.lower().strip())
    if re.search(r"\b(cancion|nana|arrullo|letra de|himno|cuna)\b", t):
        return "cancion"
    if re.search(r"\b(poema|poesia|versos?|soneto|haiku|rima)\b", t):
        return "poema"
    if re.search(r"\b(cuento|historia|relato|fabula|leyenda|narra)\b", t):
        return "cuento"
    if "?" in t or re.match(
        r"^(por favor\s+)?(explica|explicame|que es|que son|como|por que|porque|cual|cuales|quien|quienes|cuando|donde|define|"
        r"dime|hablame|ensename|en que consiste|para que sirve|describe como)\b", t
    ):
        return "explicar"
    return "escena"


def tema_principal(texto: str) -> str:
    """Lo que la persona pide, sin la fórmula de la petición: «escribe un poema sobre el mar» → «el mar»."""
    t = texto.strip().strip("¿¡").rstrip(" .!?")
    t = re.sub(
        r"^(por favor[, ]*)?((escr[ií]be(me)?|cr[eé]a(me)?|haz(me)?|dame|genera|quiero|necesito|puedes|podr[ií]as|dibuja|"
        r"cu[eé]ntame|h[aá]blame|expl[ií]ca(me)?|describe|dime|ens[eé][ñn]ame)\s+)+",
        "", t, flags=re.I,
    )
    t = re.sub(
        r"^((un|una|el|la)\s+)?(poema|poes[ií]a|canci[oó]n|nana|cuento|historia|relato|f[aá]bula|leyenda|versos?|soneto|haiku|texto|descripci[oó]n)"
        r"(\s+de\s+cuna)?(\s+(corto|corta|breve|bonito|bonita|infantil))?"
        r"(\s+(sobre|acerca\s+de|de|del|para|que\s+hable\s+de|con))?\s+",
        "", t, flags=re.I,
    )
    return t.strip() or texto.strip()


def protagonista(tema: str, texto: str) -> tuple[str, str, str]:
    """(nombre con artículo indefinido, con artículo definido, género) del protagonista del tema."""
    m = re.search(r"\b(un|una|el|la)\s+([^\W\d_]+)", tema, flags=re.I)
    if m:
        sust, g = m.group(2).lower(), ("f" if m.group(1).lower() in ("una", "la") else "m")
    else:
        cont = contenido(tema) or contenido(texto) or ["viajero"]
        sust = cont[0]
        g = genero(sust, texto)
    return con_articulo(sust, g, False), con_articulo(sust, g, True), g


def temas_detectados(*textos: str) -> list[str]:
    """Temas ordenados por cuántas palabras los activan."""
    puntos: dict[str, float] = {}
    for i, texto in enumerate(textos):
        peso = 1.0 if i == 0 else 0.5
        for tok in palabras(texto):
            base = sin_tildes(tok)
            for nombre, tema in TEMAS.items():
                for raiz in tema["raices"]:
                    corta = len(raiz) <= 3 or raiz in EXACTAS
                    if (corta and base in (raiz, raiz + "s", raiz + "es")) or (not corta and base.startswith(raiz)):
                        puntos[nombre] = puntos.get(nombre, 0) + peso
                        break
    return [n for n, _ in sorted(puntos.items(), key=lambda x: -x[1])]


def objetos_detectados(*textos: str) -> list[str]:
    bases = {sin_tildes(t) for texto in textos for t in palabras(texto)}
    return [nombre for nombre, (claves, _) in OBJETOS.items() if any(c in bases for c in claves)]


def tema(nombre: str) -> dict:
    return TEMAS.get(nombre, GENERAL)
