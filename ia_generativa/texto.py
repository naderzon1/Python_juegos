"""Modelo de lenguaje generativo: cadena de Markov de n-gramas con interpolación.

Se entrena en el momento (tarda milisegundos) con el corpus que corresponde
al prompt. Para generar mezcla la probabilidad de orden 2 (dos palabras de
contexto) con la de orden 1, lo que le permite saltar entre frases del corpus
y producir frases que no existen en él. Las frases copiadas literalmente se
descartan y se vuelven a generar.
"""

from __future__ import annotations

import random
import re
from collections import Counter, defaultdict

from . import corpus
from .temas import NOMBRES, Interpretacion, normalizar, palabras_de

INICIO, FIN = "<s>", "</s>"
_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+|[,;:]")
_FRASE = re.compile(r"[^.!?\n]+[.!?]")

# Palabras que no sirven para orientar el tema.
_VACIAS = set("""de la el los las un una y en con por para del al que como se su sus es
mas muy sin sobre bajo hacia desde entre cada todo nadie hay lo le les a o u ni yo tu mi""".split())


def _tokens(frase: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(frase)]


def _unir(tokens: list[str]) -> str:
    texto = ""
    for t in tokens:
        texto += t if t in ",;:" or not texto else " " + t
    return texto[:1].upper() + texto[1:]


class ModeloMarkov:
    def __init__(self, orden: int = 2, peso_bajo: float = 0.0):
        self.orden = orden
        self.peso_bajo = peso_bajo  # cuánto pesa el orden 1 al mezclar
        self.tabla: dict[int, dict[tuple, Counter]] = {
            k: defaultdict(Counter) for k in range(1, orden + 1)}
        self.originales: set[str] = set()
        self.ngramas: set[tuple] = set()  # de orden + 2 palabras, para medir saltos
        self.frases_entrenadas = 0

    def entrenar(self, texto: str) -> None:
        for frase in _FRASE.findall(texto):
            toks = _tokens(frase)
            if len(toks) < 3:
                continue
            self.originales.add(" ".join(toks))
            self.frases_entrenadas += 1
            sec = [INICIO] * self.orden + toks + [FIN]
            n = self.orden + 2
            self.ngramas.update(tuple(sec[i:i + n]) for i in range(len(sec) - n + 1))
            for i in range(self.orden, len(sec)):
                for k in range(1, self.orden + 1):
                    self.tabla[k][tuple(sec[i - k:i])][sec[i]] += 1

    @property
    def vocabulario(self) -> int:
        return len({t for c in self.tabla[1].values() for t in c})

    def _candidatos(self, contexto: list[str]) -> dict[str, float]:
        mezcla: dict[str, float] = defaultdict(float)
        pesos = {self.orden: 1.0 - self.peso_bajo, 1: self.peso_bajo}
        if self.orden == 1:
            pesos = {1: 1.0}
        for k, peso in pesos.items():
            # Al inicio de frase solo vale el contexto completo de inicio.
            if peso <= 0 or (k == 1 and contexto[-1] == INICIO):
                continue
            cont = self.tabla[k].get(tuple(contexto[-k:]))
            if not cont:
                continue
            total = sum(cont.values())
            for tok, n in cont.items():
                mezcla[tok] += peso * n / total
        return mezcla

    def generar_frase(self, rng: random.Random, foco: set[str],
                      min_tok: int = 5, max_tok: int = 20) -> list[str]:
        """Devuelve la frase, o una lista vacía si no terminó de forma natural."""
        contexto = [INICIO] * self.orden
        salida: list[str] = []
        while True:
            if len(salida) >= max_tok:
                return []
            cand = self._candidatos(contexto)
            if not cand:
                break
            if len(salida) < min_tok:
                cand.pop(FIN, None)
                if not cand:
                    break
            tokens = list(cand)
            pesos = []
            for t in tokens:
                p = cand[t]
                if t not in _VACIAS and normalizar(t)[:5] in foco:
                    p *= 4.0  # el tema del prompt atrae al modelo
                pesos.append(p)
            elegido = rng.choices(tokens, pesos)[0]
            if elegido == FIN:
                break
            salida.append(elegido)
            contexto.append(elegido)
        while salida and salida[-1] in ",;:":
            salida.pop()
        return salida

    def es_original(self, tokens: list[str]) -> bool:
        return " ".join(tokens) not in self.originales

    def saltos(self, tokens: list[str]) -> int:
        """Cuántas veces la frase salta de una frase del corpus a otra.

        0 saltos es una copia; 1 o 2 suelen dar frases nuevas y gramaticales;
        más saltos aumentan el riesgo de frases sin sentido.
        """
        sec = [INICIO] * self.orden + tokens + [FIN]
        n = self.orden + 2
        return sum(1 for i in range(len(sec) - n + 1) if tuple(sec[i:i + n]) not in self.ngramas)


def entrenar_para(interp: Interpretacion, extra: str = "") -> ModeloMarkov:
    modelo = ModeloMarkov()
    modelo.entrenar(corpus.GENERAL)
    modelo.entrenar(corpus.ESCENAS[interp.escena])
    modelo.entrenar(corpus.HORAS[interp.hora])
    modelo.entrenar(corpus.ANIMOS[interp.animo])
    if extra:
        modelo.entrenar(extra)
    return modelo


def generar_texto(interp: Interpretacion, modo: str = "poema", extra: str = "") -> dict:
    """Genera título y cuerpo. `modo` es "poema" o "relato"."""
    rng = random.Random(interp.semilla ^ 0x7E57)
    modelo = entrenar_para(interp, extra)
    foco = {p[:5] for p in palabras_de(interp.prompt) if p not in _VACIAS and len(p) > 2}
    foco |= {normalizar(NOMBRES[interp.escena])[:5], normalizar(NOMBRES[interp.hora])[:5]}

    n_frases = 8 if modo == "poema" else 7
    # Se generan muchos candidatos y se eligen los mejores: nuevos, con pocos
    # saltos entre frases del corpus, cercanos al tema y de largo cómodo.
    candidatos: dict[str, tuple[float, list[str]]] = {}
    for _ in range(n_frases * 18):
        toks = modelo.generar_frase(rng, foco)
        if len(toks) < 5:
            continue
        clave = " ".join(toks)
        if clave in candidatos:
            continue
        saltos = modelo.saltos(toks)
        puntos = {0: -2.0, 1: 2.0, 2: 1.2, 3: -0.5}.get(saltos, -3.0)
        puntos += 1.5 * sum(1 for t in toks if t not in _VACIAS and normalizar(t)[:5] in foco)
        puntos -= 0.12 * abs(len(toks) - 11)
        puntos += rng.random() * 1.5
        candidatos[clave] = (puntos, toks)

    frases, usados, nuevas = [], set(), 0
    for puntos, toks in sorted(candidatos.values(), key=lambda c: -c[0]):
        inicio, final = ("i",) + tuple(toks[:2]), ("f",) + tuple(toks[-3:])
        if inicio in usados or final in usados:
            continue  # variedad: no dos versos que empiecen o terminen igual
        usados.update((inicio, final))
        nuevas += modelo.es_original(toks)
        frases.append(_unir(toks))
        if len(frases) == n_frases:
            break
    rng.shuffle(frases)

    if modo == "poema":
        versos = [f.rstrip(".") for f in frases]
        cuerpo = "\n".join(versos[:4]) + "\n\n" + "\n".join(versos[4:])
    else:
        frases = [f + "." for f in frases]
        cuerpo = " ".join(frases[:4]) + "\n\n" + " ".join(frases[4:])

    sust, comp = corpus.TITULOS[interp.escena]
    titulo = f"{rng.choice(sust)} {rng.choice(comp)}"
    return {
        "titulo": titulo,
        "cuerpo": cuerpo,
        "modo": modo,
        "estadisticas": {
            "frases_entrenamiento": modelo.frases_entrenadas,
            "vocabulario": modelo.vocabulario,
            "frases_nuevas": nuevas,
            "frases_total": len(frases),
        },
    }
