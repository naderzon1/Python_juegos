"""Compositor y sintetizador de música en Python puro (salida WAV).

1. Composición: la progresión de acordes sale de una cadena de Markov con
   transiciones de armonía funcional; la melodía es una caminata aleatoria
   sobre la escala que cae en notas del acorde en los tiempos fuertes y repite
   su motivo para que la pieza tenga forma (A A' B A'').
2. Síntesis: tablas de onda (aditiva), envolventes ADSR, bajo, colchón de
   acordes, batería sintetizada y un ambiente según la escena (olas, viento,
   pájaros, zumbido espacial...). Al final, un reverb sencillo y normalización.

El ánimo decide modo, tempo e instrumento; la escena, la tonalidad y el
ambiente; la hora, el registro y el brillo.
"""

from __future__ import annotations

import io
import math
from array import array
import random
import sys
import wave

from .temas import Interpretacion

SR = 22050  # frecuencia de muestreo; baja a propósito para que sea rápido en el teléfono
TABLA = 2048

ESCALAS = {
    "mayor": [0, 2, 4, 5, 7, 9, 11],
    "lidio": [0, 2, 4, 6, 7, 9, 11],
    "menor": [0, 2, 3, 5, 7, 8, 10],
    "dorico": [0, 2, 3, 5, 7, 9, 10],
    "frigio": [0, 1, 3, 5, 7, 8, 10],
    "armonica": [0, 2, 3, 5, 7, 8, 11],
}

ESTILO = {
    # escala, tempo, instrumento principal, batería, densidad de notas
    "alegre": ("mayor", 116, "pulsado", "pop", 0.85),
    "calma": ("lidio", 72, "flauta", None, 0.55),
    "triste": ("menor", 66, "piano", None, 0.6),
    "epico": ("armonica", 98, "metal", "epica", 0.8),
    "misterio": ("frigio", 78, "campana", "suave", 0.45),
}
TONICA = {"montana": 50, "bosque": 55, "mar": 53, "desierto": 52, "ciudad": 57, "espacio": 48}
AMBIENTE = {"montana": "viento", "bosque": "pajaros", "mar": "olas", "desierto": "viento",
            "ciudad": "ciudad", "espacio": "cosmos"}

# Transiciones entre grados (0 = tónica) con pesos de armonía funcional.
MARKOV_MAYOR = {0: {3: 3, 4: 3, 5: 2, 1: 1}, 1: {4: 4, 3: 1}, 2: {5: 2, 3: 2},
                3: {4: 3, 0: 2, 1: 2}, 4: {0: 4, 5: 2, 3: 1}, 5: {3: 3, 1: 2, 4: 1}, 6: {0: 1}}
MARKOV_MENOR = {0: {5: 3, 3: 3, 6: 2, 2: 1}, 1: {4: 1}, 2: {5: 2, 3: 2, 6: 1},
                3: {0: 2, 4: 2, 6: 2}, 4: {0: 3, 5: 1}, 5: {6: 3, 3: 2, 2: 1}, 6: {0: 3, 2: 2}}

RITMOS = [  # duraciones en corcheas (8 por compás); None = silencio
    [2, 2, 2, 2], [3, 1, 2, 2], [1, 1, 2, 4], [4, 2, 2], [2, 1, 1, 2, 2],
    [1, 1, 1, 1, 2, 2], [3, 3, 2], [2, 2, 4], [6, 2], [2, None, 1, 1, 2],
]


def _midi_hz(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def _tabla(armonicos: list[float]) -> list[float]:
    t = [sum(a * math.sin(2 * math.pi * (k + 1) * i / TABLA) for k, a in enumerate(armonicos))
         for i in range(TABLA)]
    m = max(abs(v) for v in t) or 1.0
    return [v / m for v in t]


INSTRUMENTOS = {
    # tabla de armónicos, ataque, caída (s, decaimiento exponencial; 0 = sostenido), vibrato
    "pulsado": (_tabla([1, 0.5, 0.33, 0.25, 0.2, 0.12]), 0.005, 0.35, 0.0),
    "flauta": (_tabla([1, 0.12, 0.06, 0.02]), 0.08, 0.0, 0.006),
    "piano": (_tabla([1, 0.55, 0.3, 0.18, 0.1, 0.06, 0.03]), 0.004, 0.9, 0.0),
    "metal": (_tabla([1 / k for k in range(1, 10)]), 0.03, 0.0, 0.004),
    "campana": (_tabla([1, 0, 0, 0.35, 0, 0, 0.2]), 0.002, 1.2, 0.0),
    "colchon": (_tabla([1, 0.25, 0.1, 0.04]), 0.0, 0.0, 0.0),
    "bajo": (_tabla([1, 0.4, 0.1]), 0.0, 0.0, 0.0),
    "seno": (_tabla([1]), 0.0, 0.0, 0.0),
}


class Mezcla:
    def __init__(self, segundos: float):
        self.n = int(segundos * SR)
        self.l = [0.0] * self.n
        self.r = [0.0] * self.n

    def nota(self, inicio: float, dur: float, hz: float, inst: str, vol: float,
             pan: float = 0.0, liberar: float = 0.08, coro: float = 0.0) -> None:
        """Una nota con envolvente. `coro` suma una segunda voz desafinada."""
        tabla, ataque, caida, vib = INSTRUMENTOS[inst]
        i0 = int(inicio * SR)
        if i0 >= self.n:
            return
        fin = min(self.n, i0 + int((dur + liberar) * SR))
        paso = hz * TABLA / SR
        paso2 = paso * (1 + coro)
        gl, gr = vol * math.sqrt(0.5 * (1 - pan)), vol * math.sqrt(0.5 * (1 + pan))
        if coro:
            gl, gr = gl * 0.6, gr * 0.6
        at = max(1, int(ataque * SR))
        sost = max(at, int(dur * SR))
        rel = max(1, int(liberar * SR))
        dec = math.exp(-1.0 / (caida * SR)) if caida else 1.0
        l, r, t = self.l, self.r, tabla
        mask = TABLA - 1
        fase = fase2 = 0.0
        e_dec = 1.0
        # La envolvente se calcula cada 32 muestras (tasa de control): es
        # inaudible y hace el bucle mucho más rápido en Python.
        for b in range(0, fin - i0, 32):
            k = b
            if k < at:
                env = k / at
            elif k < sost:
                env = 1.0
            else:
                env = 1 - (k - sost) / rel
                if env <= 0:
                    break
            env *= e_dec
            e_dec *= dec ** 32
            p = paso * (1 + vib * math.sin(k * 0.00148)) if vib else paso
            el, er = env * gl, env * gr
            if coro:
                for j in range(i0 + b, min(fin, i0 + b + 32)):
                    s = t[int(fase) & mask] + t[int(fase2) & mask]
                    fase += p
                    fase2 += paso2
                    l[j] += s * el
                    r[j] += s * er
            else:
                for j in range(i0 + b, min(fin, i0 + b + 32)):
                    s = t[int(fase) & mask]
                    fase += p
                    l[j] += s * el
                    r[j] += s * er

    def campana(self, inicio: float, dur: float, hz: float, vol: float, pan: float) -> None:
        """Parciales inarmónicos (como una campana o un vibráfono)."""
        seno, mask = INSTRUMENTOS["seno"][0], TABLA - 1
        gl, gr = math.sqrt(0.5 * (1 - pan)), math.sqrt(0.5 * (1 + pan))
        i0 = int(inicio * SR)
        for ratio, a, d in ((1.0, 1.0, 1.4), (2.76, 0.45, 0.7), (5.4, 0.25, 0.35)):
            fin = min(self.n, i0 + int((d * 2.2) * SR))
            paso = hz * ratio * TABLA / SR
            dec32 = math.exp(-32.0 / (d * SR))
            e, fase = vol * a, 0.0
            for b in range(0, max(0, fin - i0), 32):
                el, er = e * gl * min(1.0, b / 64), e * gr * min(1.0, b / 64)
                for j in range(i0 + b, min(fin, i0 + b + 32)):
                    s = seno[int(fase) & mask]
                    fase += paso
                    self.l[j] += s * el
                    self.r[j] += s * er
                e *= dec32


# ------------------------------------------------------------- batería

def _bombo(m: Mezcla, t: float, vol: float) -> None:
    i0 = int(t * SR)
    fase = 0.0
    for k in range(min(int(0.32 * SR), m.n - i0)):
        x = k / SR
        f = 45 + 95 * math.exp(-x * 28)
        fase += 2 * math.pi * f / SR
        s = math.sin(fase) * math.exp(-x * 9) * vol
        m.l[i0 + k] += s
        m.r[i0 + k] += s


def _caja(m: Mezcla, t: float, vol: float, rng: random.Random) -> None:
    i0 = int(t * SR)
    for k in range(min(int(0.2 * SR), m.n - i0)):
        x = k / SR
        s = (rng.uniform(-1, 1) * 0.7 + math.sin(2 * math.pi * 185 * x) * 0.5) * math.exp(-x * 22) * vol
        m.l[i0 + k] += s
        m.r[i0 + k] += s


def _platillo(m: Mezcla, t: float, vol: float, rng: random.Random, pan: float = 0.25) -> None:
    i0 = int(t * SR)
    prev = 0.0
    gl, gr = math.sqrt(0.5 * (1 - pan)), math.sqrt(0.5 * (1 + pan))
    for k in range(min(int(0.06 * SR), m.n - i0)):
        n = rng.uniform(-1, 1)
        s = (n - prev) * math.exp(-k / SR * 70) * vol  # diferencia = filtro paso alto
        prev = n
        m.l[i0 + k] += s * gl
        m.r[i0 + k] += s * gr


def _timbal(m: Mezcla, t: float, vol: float, hz: float) -> None:
    i0 = int(t * SR)
    fase = 0.0
    for k in range(min(int(0.5 * SR), m.n - i0)):
        x = k / SR
        fase += 2 * math.pi * hz * (1 + 0.5 * math.exp(-x * 20)) / SR
        s = math.sin(fase) * math.exp(-x * 6) * vol
        m.l[i0 + k] += s
        m.r[i0 + k] += s


# ------------------------------------------------------------ ambiente

def _ambiente(m: Mezcla, tipo: str, rng: random.Random, tonica: int, vol: float) -> None:
    n = m.n
    if tipo in ("olas", "viento", "ciudad"):
        lento = {"olas": 0.13, "viento": 0.07, "ciudad": 0.05}[tipo]
        fl, fr = 0.0, 0.0
        f2l, f2r = 0.0, 0.0
        fase = rng.uniform(0, 6.28)
        ruido = [rng.uniform(-1, 1) for _ in range(65537)]
        nr = len(ruido)
        L, R = m.l, m.r
        for b in range(0, n, 64):
            x = b / SR
            lfo = 0.5 + 0.5 * math.sin(2 * math.pi * lento * x + fase)
            if tipo == "olas":
                amp = lfo ** 3 * 1.4 + 0.08
                corte = 0.04 + 0.12 * lfo
            elif tipo == "viento":
                amp = 0.25 + 0.75 * lfo * (0.6 + 0.4 * math.sin(x * 1.3 + fase))
                corte = 0.02 + 0.05 * lfo
            else:  # rumor lejano de ciudad
                amp, corte = 0.5 + 0.2 * lfo, 0.015
            g = amp * vol * 3
            c2 = corte * 2
            for k in range(b, min(n, b + 64)):
                fl += (ruido[k % nr] - fl) * corte
                fr += (ruido[(k + 30011) % nr] - fr) * corte
                f2l += (fl - f2l) * c2
                f2r += (fr - f2r) * c2
                L[k] += f2l * g
                R[k] += f2r * g
    elif tipo == "pajaros":
        t = rng.uniform(0.5, 2.0)
        while t < n / SR - 1:
            base = rng.uniform(2200, 3800)
            pan = rng.uniform(-0.8, 0.8)
            for j in range(rng.randint(2, 5)):  # un canto = varios trinos
                i0 = int((t + j * 0.11) * SR)
                largo = int(rng.uniform(0.05, 0.09) * SR)
                fase = 0.0
                sube = rng.choice([-1, 1])
                for k in range(min(largo, n - i0)):
                    p = k / largo
                    fase += 2 * math.pi * base * (1 + sube * 0.25 * p) / SR
                    s = math.sin(fase) * math.sin(math.pi * p) * vol * 0.5
                    m.l[i0 + k] += s * (1 - pan) * 0.7
                    m.r[i0 + k] += s * (1 + pan) * 0.7
            t += rng.uniform(1.2, 4.0)
    elif tipo == "cosmos":
        # Zumbido grave (tónica y quinta) con batido lento entre dos voces.
        m.nota(0, n / SR, _midi_hz(tonica - 24), "bajo", vol * 14, liberar=0.1, coro=0.004)
        m.nota(0, n / SR, _midi_hz(tonica - 17), "colchon", vol * 6, pan=0.3, liberar=0.1, coro=0.003)
        t = 1.0
        while t < n / SR - 2:  # destellos agudos
            m.campana(t, 1.5, _midi_hz(tonica + 24 + rng.choice([0, 7, 12, 14])), vol * 0.5,
                      rng.uniform(-0.9, 0.9))
            t += rng.uniform(1.5, 4.5)


# ---------------------------------------------------------- composición

def _progresion(rng: random.Random, menor: bool, compases: int) -> list[int]:
    tabla = MARKOV_MENOR if menor else MARKOV_MAYOR
    frase = [0]
    while len(frase) < 4:
        opciones = tabla[frase[-1]]
        frase.append(rng.choices(list(opciones), list(opciones.values()))[0])
    # Forma: la frase se repite y termina con cadencia (dominante -> tónica).
    prog = (frase * (compases // 4 + 1))[:compases]
    prog[-2], prog[-1] = 4, 0
    return prog


def _acorde(grado: int, escala: list[int]) -> list[int]:
    """Semitonos del acorde tríada construido sobre el grado."""
    return [escala[(grado + i) % 7] + 12 * ((grado + i) // 7) for i in (0, 2, 4)]


def _melodia(rng: random.Random, prog: list[int], escala: list[int], densidad: float):
    """Devuelve [(compás, corchea_inicio, duración, grado_absoluto)]."""
    motivos = {}
    notas = []
    pos = 7  # grado absoluto (7 = tónica una octava arriba)
    forma = ["A", "A", "B", "A"]
    for c, grado in enumerate(prog):
        seccion = forma[(c // 2) % 4]
        clave = (seccion, c % 2)
        acorde = {(grado + i) % 7 for i in (0, 2, 4)}
        if clave in motivos and c < len(prog) - 1:
            # Repetición del motivo, ajustada al acorde actual.
            ritmo, saltos = motivos[clave]
        else:
            ritmo = rng.choice(RITMOS) if rng.random() < densidad else rng.choice([[4, 4], [6, 2], [8]])
            saltos = [rng.choices([-2, -1, 0, 1, 2, 3, -3], [1, 3, 1, 3, 1, 0.4, 0.4])[0] for _ in ritmo]
            motivos[clave] = (ritmo, saltos)
        t = 0
        for j, (dur, salto) in enumerate(zip(ritmo, saltos)):
            if dur is None:
                t += 1
                continue
            pos = max(2, min(13, pos + salto))
            if t in (0, 4) and pos % 7 not in acorde:  # tiempo fuerte -> nota del acorde
                pos += min((d for d in (-1, 1, -2, 2) if (pos + d) % 7 in acorde), key=abs)
            notas.append((c, t, dur, pos))
            t += dur
    # Final en la tónica más cercana, larga.
    notas = [n for n in notas if n[0] < len(prog) - 1]
    notas.append((len(prog) - 1, 0, 8, min((0, 7, 14), key=lambda g: abs(g - pos))))
    return notas


def generar_sonido(interp: Interpretacion, compases: int = 8) -> bytes:
    """Compone y sintetiza la pieza; devuelve los bytes de un WAV estéreo de 16 bits."""
    rng = random.Random(interp.semilla ^ 0x50D0)
    nombre_escala, tempo, inst, bateria, densidad = ESTILO[interp.animo]
    escala = ESCALAS[nombre_escala]
    tonica = TONICA[interp.escena] + (-12 if interp.hora == "noche" else 0)
    if interp.hora == "noche":
        tempo = int(tempo * 0.9)
    tempo = int(tempo * rng.uniform(0.95, 1.05))
    corchea = 60 / tempo / 2
    compas = corchea * 8
    menor = escala[2] == 3
    prog = _progresion(rng, menor, compases)
    total = compas * compases + 3.0
    m = Mezcla(total)

    def nota_escala(grado_abs: int, base: int) -> int:
        return base + escala[grado_abs % 7] + 12 * (grado_abs // 7)

    # Colchón de acordes y bajo.
    for c, grado in enumerate(prog):
        t0 = c * compas
        for i, semi in enumerate(_acorde(grado, escala)):
            m.nota(t0, compas, _midi_hz(tonica + semi) * 0.997, "colchon", 0.075,
                   pan=(i - 1) * 0.5, liberar=0.6, coro=0.006)
        raiz = _midi_hz(tonica - 12 + escala[grado % 7])
        if bateria in ("pop", "epica"):
            for k in range(4):
                m.nota(t0 + k * corchea * 2, corchea * 1.6, raiz, "bajo", 0.16)
        else:
            m.nota(t0, compas * 0.95, raiz, "bajo", 0.13, liberar=0.4)

    # Melodía.
    melodia_base = tonica + 12
    for c, t, dur, pos in _melodia(rng, prog, escala, densidad):
        inicio = c * compas + t * corchea
        hz = _midi_hz(nota_escala(pos, melodia_base))
        pan = rng.uniform(-0.25, 0.25)
        if inst == "campana":
            m.campana(inicio, dur * corchea, hz, 0.16, pan)
        else:
            m.nota(inicio, dur * corchea * 0.92, hz, inst, 0.2, pan=pan, liberar=0.12)

    # Batería.
    if bateria:
        for c in range(compases):
            t0 = c * compas
            for k in range(8):
                t = t0 + k * corchea
                if bateria == "pop":
                    if k in (0, 4) or (k == 7 and rng.random() < 0.3):
                        _bombo(m, t, 0.5)
                    if k in (2, 6):
                        _caja(m, t, 0.18, rng)
                    _platillo(m, t, 0.1 if k % 2 else 0.16, rng)
                elif bateria == "epica":
                    if k in (0, 3, 6):
                        _bombo(m, t, 0.55)
                    if k == 4:
                        _caja(m, t, 0.22, rng)
                    if c % 4 == 3 and k >= 4:  # redoble de timbales al final de cada frase
                        _timbal(m, t, 0.3, _midi_hz(tonica - 12 + (7 - k) * 2))
                elif bateria == "suave" and k in (0, 5):
                    _platillo(m, t, 0.06, rng, pan=-0.4)

    _ambiente(m, AMBIENTE[interp.escena], rng, tonica, 0.05)
    _reverb(m)
    return _wav(m)


def _reverb(m: Mezcla) -> None:
    """Dos filtros peine por canal con tiempos distintos: da espacio y anchura."""
    for canal, retardos in ((m.l, (1557, 2117)), (m.r, (1617, 1949))):
        seco = canal[:]
        for d in retardos:
            buf = [0.0] * m.n
            for k in range(d, m.n):
                buf[k] = seco[k - d] + buf[k - d] * 0.62
            for k in range(m.n):
                canal[k] += buf[k] * 0.09


def _wav(m: Mezcla) -> bytes:
    pico = max(max(map(abs, m.l)), max(map(abs, m.r))) or 1.0
    g = 0.89 / pico
    fundido = int(1.5 * SR)
    datos = array("h", bytes(4 * m.n))
    for k in range(m.n):
        f = g * 32767 * min(1.0, (m.n - k) / fundido)
        datos[2 * k] = int(m.l[k] * f)
        datos[2 * k + 1] = int(m.r[k] * f)
    if sys.byteorder == "big":
        datos.byteswap()
    salida = io.BytesIO()
    with wave.open(salida, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(datos.tobytes())
    return salida.getvalue()
