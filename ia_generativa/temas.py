"""Interpretación del prompt: escena, hora del día y ánimo.

Los tres modelos (texto, imagen y sonido) se condicionan con la misma
interpretación, así el resultado es coherente entre sí: un "mar triste de
noche" produce un texto sobre el mar nocturno, una imagen de mar con luna y
una pieza lenta en modo menor con sonido de olas.
"""

from __future__ import annotations

import hashlib
import random
import re
import unicodedata
from dataclasses import dataclass, field

ESCENAS = ("montana", "bosque", "mar", "desierto", "ciudad", "espacio")
HORAS = ("amanecer", "dia", "atardecer", "noche")
ANIMOS = ("alegre", "calma", "triste", "epico", "misterio")

NOMBRES = {
    "montana": "montaña", "bosque": "bosque", "mar": "mar", "desierto": "desierto",
    "ciudad": "ciudad", "espacio": "espacio", "amanecer": "amanecer", "dia": "día",
    "atardecer": "atardecer", "noche": "noche", "alegre": "alegre", "calma": "calma",
    "triste": "triste", "epico": "épico", "misterio": "misterio",
}

# Raíces de palabra (sin tildes) que activan cada categoría.
PALABRAS = {
    "montana": ["montan", "cordiller", "pico", "cumbre", "nieve", "nevad", "volcan", "roca",
                "sierra", "andes", "colina", "cerro", "valle", "mountain"],
    "bosque": ["bosque", "arbol", "selva", "jungla", "hoja", "pino", "verde", "musgo",
               "naturaleza", "flor", "jardin", "forest", "tree", "parque"],
    "mar": ["mar", "ocean", "playa", "ola", "costa", "isla", "barco", "puerto", "lago",
            "agua", "rio", "sea", "beach", "marea", "pez"],
    "desierto": ["desierto", "duna", "arena", "sahara", "oasis", "cactus", "seco", "arido",
                 "desert", "calor"],
    "ciudad": ["ciudad", "urban", "calle", "edificio", "rascacielo", "metropoli", "neon",
               "trafico", "city", "barrio", "pueblo", "torre"],
    "espacio": ["espacio", "galaxia", "estrella", "planeta", "nebulosa", "cosmo", "universo",
                "astronaut", "orbita", "luna", "space", "cohete", "nave", "marte", "sideral"],
    "amanecer": ["amanec", "alba", "aurora", "madrugada", "sunrise", "manana"],
    "dia": ["dia", "mediodia", "soleado", "sol", "tarde clara", "luminos", "day", "verano"],
    "atardecer": ["atardec", "ocaso", "crepusculo", "puesta", "sunset", "anochecer", "dorad"],
    "noche": ["noche", "nocturn", "oscur", "medianoche", "night", "sueno", "estrellad",
              "luna llena"],
    "alegre": ["alegr", "feliz", "content", "divert", "fiesta", "brillante", "happy",
               "esperanz", "celebr", "jugar", "risa"],
    "calma": ["calma", "tranquil", "paz", "seren", "relaj", "suave", "silencio", "quiet",
              "lent", "medit", "descans"],
    "triste": ["trist", "melancol", "nostalg", "soledad", "solo", "lluvia", "llanto", "pena",
               "perdid", "sad", "olvido", "adios", "gris"],
    "epico": ["epic", "heroe", "heroic", "batalla", "guerr", "aventur", "glori", "poder",
              "tormenta", "dragon", "conquist", "valient", "fuerza"],
    "misterio": ["misterio", "enigma", "secreto", "extran", "fantasma", "niebla",
                 "sombra", "magia", "mistic", "antiguo", "ruina", "oculto", "bruma"],
}


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar palabras."""
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def palabras_de(texto: str) -> list[str]:
    return re.findall(r"[a-zñ]+", normalizar(texto))


@dataclass
class Interpretacion:
    prompt: str
    escena: str
    hora: str
    animo: str
    semilla: int
    detectado: dict = field(default_factory=dict)

    def describir(self) -> dict:
        return {
            "escena": NOMBRES[self.escena],
            "hora": NOMBRES[self.hora],
            "animo": NOMBRES[self.animo],
            "semilla": self.semilla,
            "detectado": self.detectado,
        }


def _puntuar(palabras: list[str], texto_norm: str, categorias) -> dict[str, int]:
    puntos = {}
    for cat in categorias:
        total = 0
        for raiz in PALABRAS[cat]:
            if " " in raiz:
                total += 2 * texto_norm.count(raiz)
            else:
                # Raíces cortas ("mar", "sol", "dia") deben coincidir con la palabra
                # completa o con su plural; si no, "mar" aparecería en "marte".
                corta = len(raiz) <= 3
                for p in palabras:
                    if (p in (raiz, raiz + "s", raiz + "es")) if corta else p.startswith(raiz):
                        total += 2 if p == raiz else 1
        if total:
            puntos[cat] = total
    return puntos


def semilla_de(prompt: str) -> int:
    return int.from_bytes(hashlib.sha256(prompt.strip().lower().encode()).digest()[:4], "big")


def interpretar(prompt: str, semilla: int | None = None) -> Interpretacion:
    """Convierte el prompt en (escena, hora, ánimo).

    Lo que el prompt no dice se elige al azar con la semilla, así el mismo
    prompt con la misma semilla siempre produce el mismo resultado.
    """
    if semilla is None:
        semilla = semilla_de(prompt)
    rng = random.Random(semilla)
    texto_norm = normalizar(prompt)
    palabras = palabras_de(prompt)

    elegidos, detectado = {}, {}
    for nombre, categorias in (("escena", ESCENAS), ("hora", HORAS), ("animo", ANIMOS)):
        puntos = _puntuar(palabras, texto_norm, categorias)
        if puntos:
            mejor = max(puntos.values())
            empatados = [c for c in categorias if puntos.get(c) == mejor]
            elegidos[nombre] = empatados[0]
            detectado[nombre] = True
        else:
            elegidos[nombre] = rng.choice(categorias)
            detectado[nombre] = False

    # "Luna" o "estrellas" sin más contexto describen la noche, no el espacio exterior.
    if elegidos["escena"] == "espacio" and not detectado["hora"]:
        elegidos["hora"] = "noche"
    return Interpretacion(prompt, elegidos["escena"], elegidos["hora"], elegidos["animo"],
                          semilla, detectado)
