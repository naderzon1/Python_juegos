"""Pruebas del Estudio Generativo. Ejecutar: python -m unittest discover tests"""

import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
import wave
import zlib
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ia_generativa import generar, interpretar  # noqa: E402
from ia_generativa.imagen import generar_imagen  # noqa: E402
from ia_generativa.servidor import Manejador  # noqa: E402
from ia_generativa.sonido import generar_sonido  # noqa: E402
from ia_generativa.temas import ANIMOS, ESCENAS, HORAS, Interpretacion  # noqa: E402
from ia_generativa.texto import ModeloMarkov, generar_texto  # noqa: E402


def leer_png(datos):
    assert datos[:8] == b"\x89PNG\r\n\x1a\n"
    ancho = int.from_bytes(datos[16:20], "big")
    alto = int.from_bytes(datos[20:24], "big")
    i, idat = 8, b""
    while i < len(datos):
        n = int.from_bytes(datos[i:i + 4], "big")
        if datos[i + 4:i + 8] == b"IDAT":
            idat += datos[i + 8:i + 8 + n]
        i += 12 + n
    return ancho, alto, zlib.decompress(idat)


class Interpretacion_(unittest.TestCase):
    def test_detecta_escena_hora_animo(self):
        i = interpretar("un mar triste de noche")
        self.assertEqual((i.escena, i.hora, i.animo), ("mar", "noche", "triste"))
        self.assertTrue(all(i.detectado.values()))

    def test_tildes_y_mayusculas(self):
        i = interpretar("MONTAÑAS ÉPICAS al Atardecer")
        self.assertEqual((i.escena, i.hora, i.animo), ("montana", "atardecer", "epico"))

    def test_raices_cortas_no_confunden(self):
        self.assertEqual(interpretar("viaje a marte").escena, "espacio")

    def test_misma_semilla_mismo_resultado(self):
        a, b = interpretar("algo", 42), interpretar("algo", 42)
        self.assertEqual((a.escena, a.hora, a.animo), (b.escena, b.hora, b.animo))


class Texto(unittest.TestCase):
    def test_genera_frases_mayormente_nuevas(self):
        r = generar_texto(interpretar("bosque en calma al amanecer"), "poema")
        e = r["estadisticas"]
        self.assertTrue(r["titulo"])
        self.assertEqual(e["frases_total"], 8)
        self.assertGreaterEqual(e["frases_nuevas"], 4)

    def test_relato(self):
        r = generar_texto(interpretar("ciudad alegre"), "relato")
        self.assertIn(".", r["cuerpo"])

    def test_corpus_extra_amplia_vocabulario(self):
        i = interpretar("mar")
        base = generar_texto(i)["estadisticas"]["vocabulario"]
        extra = "El capitán dibujó un mapa de coral y ámbar. El capitán soñó con ballenas de cristal."
        self.assertGreater(generar_texto(i, extra=extra)["estadisticas"]["vocabulario"], base)

    def test_saltos(self):
        m = ModeloMarkov()
        m.entrenar("el gato duerme en la casa. el perro corre en la calle.")
        self.assertEqual(m.saltos("el gato duerme en la casa".split()), 0)
        self.assertGreater(m.saltos("el gato duerme en la calle".split()), 0)


class Imagen(unittest.TestCase):
    def test_todas_las_escenas_dan_png_valido(self):
        for escena in ESCENAS:
            for hora in HORAS:
                i = Interpretacion("x", escena, hora, ANIMOS[len(escena) % 5], 7)
                ancho, alto, crudo = leer_png(generar_imagen(i, 64, 40))
                self.assertEqual((ancho, alto), (64, 40))
                self.assertEqual(len(crudo), 40 * (1 + 64 * 3))

    def test_reproducible(self):
        i = interpretar("desierto épico", 5)
        self.assertEqual(generar_imagen(i, 48, 32), generar_imagen(i, 48, 32))


class Sonido(unittest.TestCase):
    def test_wav_valido_en_todos_los_animos(self):
        for animo in ANIMOS:
            datos = generar_sonido(Interpretacion("x", "bosque", "dia", animo, 3), compases=4)
            with wave.open(io.BytesIO(datos)) as w:
                self.assertEqual((w.getnchannels(), w.getsampwidth()), (2, 2))
                self.assertGreater(w.getnframes() / w.getframerate(), 5)

    def test_ambientes(self):
        for escena in ESCENAS:
            datos = generar_sonido(Interpretacion("x", escena, "noche", "calma", 1), compases=4)
            self.assertGreater(len(datos), 44)


class Motor(unittest.TestCase):
    def test_generar_todo(self):
        r = generar("planeta misterioso", ancho=64, alto=40)
        self.assertEqual(set(r["tiempos"]), {"texto", "imagen", "sonido"})
        self.assertEqual(r["interpretacion"]["escena"], "espacio")


class Servidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        Manejador.carpeta = Path(cls.tmp.name)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def post(self, datos):
        req = urllib.request.Request(self.url + "/api/generar", json.dumps(datos).encode(),
                                     {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_pagina(self):
        with urllib.request.urlopen(self.url + "/") as r:
            self.assertIn(b"Estudio Generativo", r.read())

    def test_texto_y_archivo(self):
        codigo, d = self.post({"tipo": "texto", "prompt": "mar en calma"})
        self.assertEqual(codigo, 200)
        with urllib.request.urlopen(self.url + d["url"]) as r:
            self.assertIn(d["texto"]["titulo"], r.read().decode())

    def test_errores(self):
        self.assertEqual(self.post({"tipo": "texto", "prompt": ""})[0], 400)
        self.assertEqual(self.post({"tipo": "otro", "prompt": "a"})[0], 400)

    def test_no_sale_de_la_carpeta(self):
        for ruta in ("/salida/../secreto.txt", "/salida/%2e%2e%2fx.txt", "/salida/a.py"):
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(self.url + ruta)


if __name__ == "__main__":
    unittest.main()
