"""Conocimiento externo sin clave: la API pública de Wikipedia en español.

Solo se envían las palabras clave de la pregunta. Se desactiva con PRISMA_WIKIPEDIA=0.
"""

from __future__ import annotations

import json
import os
import re
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API = "https://es.wikipedia.org/w/api.php"
AGENTE = "PrismaGenerativo/1.0 (aplicación local de aprendizaje)"


def activo() -> bool:
    return os.environ.get("PRISMA_WIKIPEDIA", "1") != "0"


def buscar(consulta: str, timeout: float = 5.0) -> dict | None:
    """Introducción en texto plano del artículo que mejor coincide, o None."""
    if not activo() or not consulta.strip():
        return None
    params = {
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "search", "gsrsearch": consulta, "gsrlimit": "1",
        "prop": "extracts", "exintro": "1", "explaintext": "1", "redirects": "1",
    }
    try:
        with urlopen(Request(f"{API}?{urlencode(params)}", headers={"User-Agent": AGENTE}), timeout=timeout) as r:
            datos = json.load(r)
    except Exception as error:  # sin red, DNS, tiempo agotado…
        print(f"[prisma] Wikipedia no disponible: {error}")
        return None
    paginas = datos.get("query", {}).get("pages", [])
    if not paginas or not paginas[0].get("extract"):
        return None
    p = paginas[0]
    return {"titulo": p["title"], "texto": limpiar(p["extract"]),
            "url": "https://es.wikipedia.org/wiki/" + quote(p["title"].replace(" ", "_"))}


def limpiar(texto: str) -> str:
    for _ in range(2):  # paréntesis anidados: pronunciaciones, fechas, etimologías
        texto = re.sub(r"\s*\([^()]*\)", "", texto)
    texto = re.sub(r"\[\d+\]", "", texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    return re.sub(r"\s+([,.;:])", r"\1", texto).strip()


def oraciones(texto: str) -> list[str]:
    partes = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])", texto.replace("\n", " "))
    return [p.strip() for p in partes if len(p.split()) >= 5 and not p.strip().endswith(":")]
