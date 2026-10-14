"""Bloques: puzle de piezas que caen, al estilo de los clásicos, con música y efectos de sonido.

Encaja las piezas para completar filas: cada fila completa desaparece y suma puntos.
Cada 10 filas sube el nivel y las piezas caen más rápido. Pierdes si las piezas llegan arriba.

Requiere:  pip install pygame
La música y los efectos se sintetizan al arrancar (no usa archivos de sonido).

Controles:
  ← / →        mover               ↓         bajar más rápido
  ↑ o X        girar a la derecha  Z         girar a la izquierda
  ESPACIO      soltar de golpe     C         guardar la pieza para después
  M música  |  P pausa  |  R reiniciar  |  ESC salir
"""
import array
import random
from pathlib import Path

import pygame

COLUMNAS, FILAS = 10, 20
OCULTAS = 2              # filas sobre el tablero visible donde nacen las piezas
CELDA = 30
MARGEN = 20
ANCHO_PANEL = 210
ANCHO = MARGEN * 3 + COLUMNAS * CELDA + ANCHO_PANEL
ALTO = MARGEN * 2 + FILAS * CELDA
FPS = 60
RETARDO_REPETIR, INTERVALO_REPETIR = 0.17, 0.05  # al mantener ← o →
RETARDO_FIJAR = 0.5      # segundos que la pieza puede deslizarse cuando ya tocó fondo
MAX_AJUSTES = 15         # cuántas veces moverla así reinicia ese tiempo
T_LIMPIAR = 0.3          # duración del destello de las filas completas
PUNTOS_LINEAS = {1: 100, 2: 300, 3: 500, 4: 800}
AVISOS = {2: "¡DOBLE!", 3: "¡TRIPLE!", 4: "¡CUATRO LÍNEAS!"}
VOL_MUSICA = 0.45
ARCHIVO_RECORD = Path(__file__).resolve().with_name("bloques_record.txt")

FONDO, TABLERO, REJILLA, TEXTO, TENUE = "#101624", "#0b0f1a", "#1a2235", "#e8ecf4", "#7d88a6"

# forma de cada pieza dentro de su caja de giro, y su color
PIEZAS = {
    "I": (["....", "XXXX", "....", "...."], "#4dd0e1"),
    "O": (["XX", "XX"], "#ffd54f"),
    "T": ([".X.", "XXX", "..."], "#ba68c8"),
    "S": ([".XX", "XX.", "..."], "#81c784"),
    "Z": (["XX.", ".XX", "..."], "#e57373"),
    "J": (["X..", "XXX", "..."], "#64b5f6"),
    "L": (["..X", "XXX", "..."], "#ffb74d"),
}
# desplazamientos que se prueban si la pieza no cabe al girar (contra paredes y piso)
EMPUJES = ((0, 0), (-1, 0), (1, 0), (0, -1), (-2, 0), (2, 0))

# --- sonido: todo se sintetiza aquí ------------------------------------------------
FREC = 22050   # se ajusta a la frecuencia real del mezclador al crear los sonidos
PASO = 0.2     # duración de una corchea de la música (150 pulsos por minuto)
# melodía y bajo propios, como (nota MIDI o None para silencio, duración en corcheas)
MELODIA = [(69, 1), (72, 1), (76, 1), (81, 1), (79, 2), (76, 2),
           (77, 1), (76, 1), (74, 1), (72, 1), (74, 2), (69, 2),
           (71, 1), (74, 1), (79, 1), (74, 1), (77, 2), (76, 2),
           (76, 2), (71, 1), (68, 1), (71, 4),
           (81, 1), (79, 1), (76, 1), (72, 1), (74, 1), (76, 1), (72, 2),
           (77, 1), (81, 1), (77, 1), (74, 1), (72, 2), (74, 2),
           (76, 1), (80, 1), (83, 1), (80, 1), (76, 2), (74, 2),
           (72, 2), (71, 2), (69, 4)]
BAJO = [nota for raiz in (45, 45, 41, 41, 43, 43, 40, 40, 45, 45, 38, 38, 40, 40, 45, 45)
        for nota in ((raiz, 1), (raiz + 12, 1), (raiz + 7, 1), (raiz + 12, 1))]


def hz(nota):
    """Frecuencia de una nota MIDI (69 = la de 440 Hz)."""
    return 440 * 2 ** ((nota - 69) / 12)


def tono(pista, inicio, dur, f0, f1=None, vol=0.3, onda="cuadrada"):
    """Suma a la pista un sonido que se desliza de f0 a f1 Hz."""
    f1 = f0 if f1 is None else f1
    i0, n = int(inicio * FREC), int(dur * FREC)
    pista.extend([0.0] * (i0 + n - len(pista)))
    fase = 0.0
    for k in range(n):
        t = k / n
        fase = (fase + (f0 + (f1 - f0) * t) / FREC) % 1
        if onda == "cuadrada":
            v = 1.0 if fase < 0.5 else -1.0
        elif onda == "triangular":
            v = 4 * abs(fase - 0.5) - 1
        else:  # ruido
            v = random.uniform(-1, 1)
        # ataque y final suaves para que no haga "clic", y una caída ligera
        pista[i0 + k] += vol * v * min(1.0, k / 100, (n - k) / 400) * (1 - 0.6 * t)


def melodia(pista, notas, paso, vol, onda):
    t = 0.0
    for nota, pasos in notas:
        if nota is not None:
            tono(pista, t, pasos * paso * 0.92, hz(nota), vol=vol, onda=onda)
        t += pasos * paso


def componer(nombre):
    p = []
    if nombre == "mover":
        tono(p, 0, 0.03, 900, vol=0.12)
    elif nombre == "girar":
        tono(p, 0, 0.06, 600, 1100, vol=0.15)
    elif nombre == "fijar":
        tono(p, 0, 0.08, 160, 90, vol=0.35, onda="triangular")
    elif nombre == "soltar":
        tono(p, 0, 0.12, 700, 120, vol=0.25)
        tono(p, 0, 0.06, 0, vol=0.15, onda="ruido")
    elif nombre == "linea":
        melodia(p, [(76, 1), (81, 1), (88, 3)], 0.06, 0.25, "cuadrada")
    elif nombre == "cuatro":
        melodia(p, [(72, 1), (76, 1), (79, 1), (84, 1), (88, 1), (91, 1), (96, 5)], 0.07, 0.25, "cuadrada")
        melodia(p, [(48, 3), (55, 3), (60, 5)], 0.07, 0.3, "triangular")
    elif nombre == "nivel":
        melodia(p, [(79, 1), (84, 1), (79, 1), (84, 1), (91, 4)], 0.08, 0.25, "triangular")
    elif nombre == "fin":
        melodia(p, [(76, 2), (72, 2), (69, 2), (64, 2), (57, 6)], 0.15, 0.35, "triangular")
    else:  # musica: dura justo 8 compases para repetirse sin corte
        melodia(p, MELODIA, PASO, 0.13, "cuadrada")
        melodia(p, BAJO, PASO, 0.28, "triangular")
        n = int(64 * PASO * FREC)
        p = (p + [0.0] * n)[:n]
    return p


def crear_sonidos():
    """Devuelve {nombre: pygame.mixer.Sound}, o {} si no hay tarjeta de sonido disponible."""
    global FREC
    formato = pygame.mixer.get_init()
    if not formato:
        return {}
    FREC, tam, canales = formato
    sonidos = {}
    for nombre in ("mover", "girar", "fijar", "soltar", "linea", "cuatro", "nivel", "fin", "musica"):
        pista = [max(-1.0, min(1.0, v)) for v in componer(nombre)]
        if tam == 32:  # el mezclador trabaja con decimales
            datos = array.array("f", (v for v in pista for _ in range(canales)))
        else:
            datos = array.array("h", (int(v * 32000) for v in pista for _ in range(canales)))
        sonidos[nombre] = pygame.mixer.Sound(buffer=datos.tobytes())
    return sonidos


# --- juego -------------------------------------------------------------------------
def color(hexa, luz=0.0):
    """Color de la paleta; luz > 0 lo aclara y luz < 0 lo oscurece."""
    c = pygame.Color(hexa)
    return c.lerp((255, 255, 255), luz) if luz > 0 else c.lerp((0, 0, 0), -luz)


def leer_record():
    try:
        return int(ARCHIVO_RECORD.read_text().strip())
    except (OSError, ValueError):
        return 0


class Juego:
    def __init__(self, pantalla):
        self.pantalla = pantalla
        self.fuente = pygame.font.SysFont("consolas,dejavusansmono,couriernew", 18, bold=True)
        self.fuente_chica = pygame.font.SysFont("consolas,dejavusansmono,couriernew", 13)
        self.fuente_grande = pygame.font.SysFont("consolas,dejavusansmono,couriernew", 34, bold=True)
        self.sonidos = crear_sonidos()
        self.musica = self.sonidos.pop("musica", None)
        self.con_musica = True
        self.record = leer_record()
        self.reiniciar()

    # --- estado ---------------------------------------------------------------
    def reiniciar(self):
        self.tablero = [[None] * COLUMNAS for _ in range(FILAS + OCULTAS)]  # tipo de pieza o None
        self.bolsa = []
        self.cola = [self.sacar_de_bolsa() for _ in range(3)]
        self.guardada = None
        self.puede_guardar = True
        self.puntos = self.lineas = 0
        self.nivel = 1
        self.estado = "jugando"  # jugando, limpiando o fin
        self.pausa = False
        self.filas_llenas = []
        self.t_limpiar = 0.0
        self.aviso, self.t_aviso = "", 0.0
        self.direccion = 0       # -1 o 1 mientras se mantiene ← o →
        self.t_repetir = 0.0
        self.bajando = False
        self.nueva_pieza()
        if self.musica:
            pygame.mixer.unpause()
            self.musica.stop()
            self.musica.play(loops=-1)
            self.ajustar_musica()

    def sacar_de_bolsa(self):
        """Las piezas salen de una bolsa con las 7: nunca hay rachas largas sin una pieza."""
        if not self.bolsa:
            self.bolsa = list(PIEZAS)
            random.shuffle(self.bolsa)
        return self.bolsa.pop()

    def nueva_pieza(self, tipo=None):
        if tipo is None:
            tipo = self.cola.pop(0)
            self.cola.append(self.sacar_de_bolsa())
        self.tipo = tipo
        forma = PIEZAS[tipo][0]
        self.n = len(forma)
        self.celdas = [(x, y) for y, fila in enumerate(forma) for x, c in enumerate(fila) if c == "X"]
        # nace asomando por la primera fila visible
        self.px = (COLUMNAS - self.n) // 2
        self.py = OCULTAS - max(y for _, y in self.celdas)
        self.t_caida = self.t_fijar = 0.0
        self.ajustes = 0
        if not self.cabe(self.celdas, self.px, self.py):
            self.terminar()

    def sonar(self, nombre):
        if nombre in self.sonidos:
            self.sonidos[nombre].play()

    def ajustar_musica(self):
        if self.musica:
            self.musica.set_volume(VOL_MUSICA if self.con_musica else 0)

    def terminar(self):
        self.estado = "fin"
        if self.musica:
            self.musica.stop()
        self.sonar("fin")
        if self.puntos > self.record:
            self.record = self.puntos
            try:
                ARCHIVO_RECORD.write_text(str(self.record))
            except OSError:
                pass

    # --- reglas ---------------------------------------------------------------
    def cabe(self, celdas, px, py):
        for x, y in celdas:
            cx, cy = px + x, py + y
            if cx < 0 or cx >= COLUMNAS or cy >= FILAS + OCULTAS or (cy >= 0 and self.tablero[cy][cx]):
                return False
        return True

    def apoyada(self):
        return not self.cabe(self.celdas, self.px, self.py + 1)

    def reajustar(self):
        """Mover o girar una pieza que ya toca fondo le da un poco más de tiempo, con límite."""
        if self.apoyada() and self.ajustes < MAX_AJUSTES:
            self.t_fijar = 0.0
            self.ajustes += 1

    def mover(self, dx):
        if self.cabe(self.celdas, self.px + dx, self.py):
            self.px += dx
            self.reajustar()
            self.sonar("mover")
            return True
        return False

    def girar(self, sentido):
        if self.tipo == "O":
            return
        n = self.n
        if sentido > 0:
            nuevas = [(n - 1 - y, x) for x, y in self.celdas]
        else:
            nuevas = [(y, n - 1 - x) for x, y in self.celdas]
        for dx, dy in EMPUJES:
            if self.cabe(nuevas, self.px + dx, self.py + dy):
                self.celdas, self.px, self.py = nuevas, self.px + dx, self.py + dy
                self.reajustar()
                self.sonar("girar")
                return

    def caida_fantasma(self):
        """Fila donde caería la pieza si se suelta ahora."""
        y = self.py
        while self.cabe(self.celdas, self.px, y + 1):
            y += 1
        return y

    def soltar(self):
        destino = self.caida_fantasma()
        self.puntos += 2 * (destino - self.py)
        self.py = destino
        self.sonar("soltar")
        self.fijar()

    def guardar(self):
        if not self.puede_guardar:
            return
        self.puede_guardar = False  # solo una vez por pieza
        anterior, self.guardada = self.guardada, self.tipo
        self.nueva_pieza(anterior)
        self.sonar("girar")

    def fijar(self):
        for x, y in self.celdas:
            self.tablero[self.py + y][self.px + x] = self.tipo
        self.puede_guardar = True
        if all(self.py + y < OCULTAS for _, y in self.celdas):  # quedó entera por encima del tablero
            self.terminar()
            return
        self.filas_llenas = [f for f, fila in enumerate(self.tablero) if all(fila)]
        if not self.filas_llenas:
            self.sonar("fijar")
            self.nueva_pieza()
            return
        n = len(self.filas_llenas)
        self.puntos += PUNTOS_LINEAS[n] * self.nivel
        self.lineas += n
        self.sonar("cuatro" if n == 4 else "linea")
        if n in AVISOS:
            self.aviso, self.t_aviso = AVISOS[n], 1.5
        if 1 + self.lineas // 10 > self.nivel:
            self.nivel = 1 + self.lineas // 10
            self.aviso, self.t_aviso = f"NIVEL {self.nivel}", 1.5
            self.sonar("nivel")
        self.estado, self.t_limpiar = "limpiando", T_LIMPIAR

    def quitar_filas(self):
        restantes = [fila for f, fila in enumerate(self.tablero) if f not in self.filas_llenas]
        self.tablero = [[None] * COLUMNAS for _ in self.filas_llenas] + restantes
        self.filas_llenas = []
        self.estado = "jugando"
        self.nueva_pieza()

    def intervalo(self):
        """Segundos que tarda la pieza en bajar una fila: cada nivel es más rápido."""
        return max(0.03, (0.8 - (self.nivel - 1) * 0.007) ** (self.nivel - 1))

    # --- entrada y tiempo -------------------------------------------------------
    def manejar(self, evento):
        if evento.type == pygame.KEYDOWN:
            tecla = evento.key
            if tecla == pygame.K_r:
                self.reiniciar()
            elif tecla == pygame.K_m:
                self.con_musica = not self.con_musica
                self.ajustar_musica()
            elif tecla == pygame.K_p and self.estado != "fin":
                self.pausa = not self.pausa
                pygame.mixer.pause() if self.pausa else pygame.mixer.unpause()
            elif self.pausa or self.estado != "jugando":
                return
            elif tecla in (pygame.K_LEFT, pygame.K_RIGHT):
                self.direccion = -1 if tecla == pygame.K_LEFT else 1
                self.t_repetir = -RETARDO_REPETIR
                self.mover(self.direccion)
            elif tecla == pygame.K_DOWN:
                self.bajando = True
            elif tecla in (pygame.K_UP, pygame.K_x):
                self.girar(1)
            elif tecla == pygame.K_z:
                self.girar(-1)
            elif tecla == pygame.K_SPACE:
                self.soltar()
            elif tecla == pygame.K_c:
                self.guardar()
        elif evento.type == pygame.KEYUP:
            if evento.key == pygame.K_DOWN:
                self.bajando = False
            elif (evento.key, self.direccion) in ((pygame.K_LEFT, -1), (pygame.K_RIGHT, 1)):
                self.direccion = 0

    def actualizar(self, dt):
        if self.pausa or self.estado == "fin":
            return
        self.t_aviso -= dt
        if self.estado == "limpiando":
            self.t_limpiar -= dt
            if self.t_limpiar <= 0:
                self.quitar_filas()
            return

        # al mantener ← o → la pieza sigue moviéndose tras una breve espera
        if self.direccion:
            self.t_repetir += dt
            while self.t_repetir >= INTERVALO_REPETIR:
                self.t_repetir -= INTERVALO_REPETIR
                if not self.mover(self.direccion):
                    self.t_repetir = 0.0
                    break

        intervalo = min(self.intervalo(), 0.035) if self.bajando else self.intervalo()
        if self.apoyada():
            self.t_caida = 0.0
            self.t_fijar += dt
            if self.t_fijar >= RETARDO_FIJAR:
                self.fijar()
            return
        self.t_fijar = 0.0
        self.t_caida += dt
        while self.t_caida >= intervalo and not self.apoyada():
            self.t_caida -= intervalo
            self.py += 1
            if self.bajando:
                self.puntos += 1

    # --- dibujo -----------------------------------------------------------------
    def bloque(self, x, y, tipo, tam=CELDA, fantasma=False):
        """Dibuja un bloque con relieve en la posición de pantalla (x, y)."""
        base = PIEZAS[tipo][1]
        r = pygame.Rect(x, y, tam, tam)
        if fantasma:
            pygame.draw.rect(self.pantalla, color(base, -0.55), r.inflate(-2, -2))
            pygame.draw.rect(self.pantalla, color(base, -0.1), r.inflate(-2, -2), 2)
            return
        borde = max(2, tam // 8)
        pygame.draw.rect(self.pantalla, color(base), r)
        pygame.draw.rect(self.pantalla, color(base, 0.45), (x, y, tam, borde))
        pygame.draw.rect(self.pantalla, color(base, 0.45), (x, y, borde, tam))
        pygame.draw.rect(self.pantalla, color(base, -0.4), (x, y + tam - borde, tam, borde))
        pygame.draw.rect(self.pantalla, color(base, -0.4), (x + tam - borde, y, borde, tam))
        pygame.draw.rect(self.pantalla, color(TABLERO), r, 1)

    def en_pantalla(self, cx, cy):
        return MARGEN + cx * CELDA, MARGEN + (cy - OCULTAS) * CELDA

    def texto(self, txt, fuente, tinta, x, y, centro=False):
        img = fuente.render(txt, True, color(tinta))
        self.pantalla.blit(img, img.get_rect(center=(x, y)) if centro else (x, y))

    def miniatura(self, tipo, caja, tam=20):
        """Pieza pequeña centrada en el rectángulo caja (cola y pieza guardada)."""
        forma = PIEZAS[tipo][0]
        celdas = [(x, y) for y, fila in enumerate(forma) for x, c in enumerate(fila) if c == "X"]
        x0, x1 = min(x for x, _ in celdas), max(x for x, _ in celdas)
        y0, y1 = min(y for _, y in celdas), max(y for _, y in celdas)
        ox = caja.centerx - (x1 - x0 + 1) * tam / 2 - x0 * tam
        oy = caja.centery - (y1 - y0 + 1) * tam / 2 - y0 * tam
        for x, y in celdas:
            self.bloque(ox + x * tam, oy + y * tam, tipo, tam)

    def caja(self, titulo, rect):
        pygame.draw.rect(self.pantalla, color(TABLERO), rect, border_radius=6)
        pygame.draw.rect(self.pantalla, color(REJILLA), rect, 2, border_radius=6)
        self.texto(titulo, self.fuente_chica, TENUE, rect.x + 10, rect.y + 8)

    def dibujar(self):
        p = self.pantalla
        p.fill(color(FONDO))
        zona = pygame.Rect(MARGEN, MARGEN, COLUMNAS * CELDA, FILAS * CELDA)
        pygame.draw.rect(p, color(TABLERO), zona)
        for c in range(1, COLUMNAS):
            pygame.draw.line(p, color(REJILLA), (zona.x + c * CELDA, zona.y), (zona.x + c * CELDA, zona.bottom))
        for f in range(1, FILAS):
            pygame.draw.line(p, color(REJILLA), (zona.x, zona.y + f * CELDA), (zona.right, zona.y + f * CELDA))

        p.set_clip(zona)
        destello = self.estado == "limpiando" and int(self.t_limpiar * 20) % 2 == 0
        for cy, fila in enumerate(self.tablero):
            for cx, tipo in enumerate(fila):
                if tipo:
                    x, y = self.en_pantalla(cx, cy)
                    if destello and cy in self.filas_llenas:
                        pygame.draw.rect(p, color("#ffffff"), (x, y, CELDA, CELDA))
                    else:
                        self.bloque(x, y, tipo)
        if self.estado == "jugando":
            fy = self.caida_fantasma()
            for x, y in self.celdas:
                self.bloque(*self.en_pantalla(self.px + x, fy + y), self.tipo, fantasma=True)
            for x, y in self.celdas:
                self.bloque(*self.en_pantalla(self.px + x, self.py + y), self.tipo)
        p.set_clip(None)
        pygame.draw.rect(p, color(REJILLA), zona.inflate(4, 4), 2)

        # panel lateral
        x0 = MARGEN * 2 + COLUMNAS * CELDA
        siguientes = pygame.Rect(x0, MARGEN, ANCHO_PANEL, 220)
        self.caja("SIGUIENTES", siguientes)
        for i, tipo in enumerate(self.cola):
            self.miniatura(tipo, pygame.Rect(x0, MARGEN + 30 + i * 62, ANCHO_PANEL, 62), 22 if i == 0 else 17)
        guardada = pygame.Rect(x0, MARGEN + 232, ANCHO_PANEL, 100)
        self.caja("GUARDADA (C)", guardada)
        if self.guardada:
            self.miniatura(self.guardada, guardada.move(0, 10), 20)
        for i, (nombre, valor) in enumerate((("PUNTOS", self.puntos), ("RÉCORD", max(self.record, self.puntos)),
                                              ("NIVEL", self.nivel), ("LÍNEAS", self.lineas))):
            y = MARGEN + 348 + i * 30
            self.texto(nombre, self.fuente_chica, TENUE, x0 + 4, y + 3)
            img = self.fuente.render(str(valor), True, color(TEXTO))
            p.blit(img, img.get_rect(topright=(x0 + ANCHO_PANEL - 4, y)))
        ayuda = ["← → mover    ↓ bajar", "↑ / X girar   Z al revés", "ESPACIO soltar de golpe",
                 "M música   P pausa", "R reiniciar  ESC salir"]
        for i, linea in enumerate(ayuda):
            self.texto(linea, self.fuente_chica, TENUE, x0 + 4, MARGEN + 482 + i * 22)
        if not self.con_musica:
            self.texto("(música apagada)", self.fuente_chica, "#ef9a9a", x0 + 4, MARGEN + 590)

        if self.t_aviso > 0 and self.aviso:
            self.texto(self.aviso, self.fuente_grande, "#ffd54f", zona.centerx, zona.y + 120, centro=True)
        if self.estado == "fin" or self.pausa:
            velo = pygame.Surface(zona.size, pygame.SRCALPHA)
            velo.fill((5, 8, 16, 190))
            p.blit(velo, zona.topleft)
            if self.estado == "fin":
                self.texto("FIN DEL JUEGO", self.fuente_grande, "#ef9a9a", zona.centerx, zona.centery - 40, True)
                nuevo = self.puntos and self.puntos >= self.record
                self.texto(f"Puntos: {self.puntos}" + ("  ¡RÉCORD!" if nuevo else ""), self.fuente, TEXTO,
                           zona.centerx, zona.centery + 5, True)
                self.texto("R para jugar de nuevo", self.fuente_chica, TENUE, zona.centerx, zona.centery + 40, True)
            else:
                self.texto("PAUSA", self.fuente_grande, TEXTO, zona.centerx, zona.centery - 15, True)
                self.texto("P para seguir", self.fuente_chica, TENUE, zona.centerx, zona.centery + 25, True)


def main():
    pygame.mixer.pre_init(FREC, -16, 1, 512)
    pygame.init()
    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("Bloques - puzle de piezas que caen")
    pantalla.fill(color(FONDO))
    fuente = pygame.font.SysFont("consolas,dejavusansmono,couriernew", 18, bold=True)
    aviso = fuente.render("Preparando sonidos...", True, color(TEXTO))
    pantalla.blit(aviso, aviso.get_rect(center=(ANCHO // 2, ALTO // 2)))
    pygame.display.flip()

    juego = Juego(pantalla)
    reloj = pygame.time.Clock()
    while True:
        dt = reloj.tick(FPS) / 1000
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT or (evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE):
                pygame.quit()
                return
            juego.manejar(evento)
        juego.actualizar(min(dt, 0.1))
        juego.dibujar()
        pygame.display.flip()


if __name__ == "__main__":
    main()
