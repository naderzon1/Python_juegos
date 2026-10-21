"""Servidor web local: la interfaz se abre en el navegador del mismo teléfono.

Solo usa la biblioteca estándar. Por defecto escucha en 127.0.0.1, así que
nada sale del dispositivo; con `red=True` también lo ven otros aparatos de la
misma red Wi-Fi.
"""

from __future__ import annotations

import json
import random
import re
import socket
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .motor import generar_tipo, nombre_base
from .temas import interpretar

WEB = Path(__file__).with_name("web")
_NOMBRE_SEGURO = re.compile(r"^[a-z0-9-]+\.(png|wav|txt)$")
_TIPOS_MIME = {".png": "image/png", ".wav": "audio/wav", ".txt": "text/plain; charset=utf-8"}
# Generar es intensivo en CPU; en serie se reparte mejor la CPU del teléfono.
_cerrojo = threading.Lock()


class Manejador(BaseHTTPRequestHandler):
    carpeta: Path = Path("salida_ia")
    server_version = "EstudioGenerativo/1.0"

    def log_message(self, formato, *args):  # consola limpia
        pass

    def _enviar(self, codigo: int, cuerpo: bytes, tipo: str, extra: dict | None = None):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, codigo: int, datos: dict):
        self._enviar(codigo, json.dumps(datos, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        ruta = self.path.split("?", 1)[0]
        if ruta in ("/", "/index.html"):
            self._enviar(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif ruta.startswith("/salida/"):
            nombre = ruta[len("/salida/"):]
            archivo = self.carpeta / nombre
            if not _NOMBRE_SEGURO.match(nombre) or not archivo.is_file():
                return self._json(404, {"error": "no existe"})
            self._enviar(200, archivo.read_bytes(), _TIPOS_MIME[archivo.suffix],
                         {"Content-Disposition": f'inline; filename="{nombre}"'})
        elif ruta == "/api/salud":
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "no existe"})

    def do_POST(self):
        if self.path != "/api/generar":
            return self._json(404, {"error": "no existe"})
        try:
            largo = min(int(self.headers.get("Content-Length", 0)), 20_000)
            datos = json.loads(self.rfile.read(largo) or b"{}")
            prompt = str(datos.get("prompt", "")).strip()[:300]
            tipo = datos.get("tipo")
            modo = "relato" if datos.get("modo") == "relato" else "poema"
            semilla = datos.get("semilla")
            semilla = int(semilla) % 2**32 if semilla not in (None, "") else None
        except (ValueError, TypeError):
            return self._json(400, {"error": "petición inválida"})
        if not prompt:
            return self._json(400, {"error": "escribe una descripción"})
        if tipo not in ("texto", "imagen", "sonido", "interpretar"):
            return self._json(400, {"error": "tipo inválido"})

        interp = interpretar(prompt, semilla)
        respuesta = {"interpretacion": interp.describir()}
        if tipo == "interpretar":
            return self._json(200, respuesta)
        with _cerrojo:
            inicio = time.perf_counter()
            resultado = generar_tipo(interp, tipo, modo)
            respuesta["segundos"] = round(time.perf_counter() - inicio, 2)
        base = nombre_base(prompt, interp.semilla)
        self.carpeta.mkdir(parents=True, exist_ok=True)
        if tipo == "texto":
            respuesta["texto"] = resultado
            (self.carpeta / f"{base}.txt").write_text(
                f"{resultado['titulo']}\n\n{resultado['cuerpo']}\n", encoding="utf-8")
            respuesta["url"] = f"/salida/{base}.txt"
        else:
            ext = "png" if tipo == "imagen" else "wav"
            (self.carpeta / f"{base}.{ext}").write_bytes(resultado)
            respuesta["url"] = f"/salida/{base}.{ext}?v={random.randrange(10**9)}"
            respuesta["bytes"] = len(resultado)
        self._json(200, respuesta)


def _ip_local() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _carpeta_escribible(preferida: Path) -> Path:
    """Algunas apps de Python para móvil no dejan escribir junto al script."""
    for carpeta in (preferida, Path(tempfile.gettempdir()) / "salida_ia"):
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
            prueba = carpeta / ".prueba"
            prueba.write_bytes(b"")
            prueba.unlink()
            return carpeta
        except OSError:
            continue
    raise SystemExit("No hay ninguna carpeta donde guardar los resultados.")


def iniciar(puerto: int = 8000, red: bool = False, abrir: bool = True,
            carpeta: Path | None = None) -> None:
    Manejador.carpeta = _carpeta_escribible(carpeta or Path.cwd() / "salida_ia")
    host = "0.0.0.0" if red else "127.0.0.1"
    for intento in range(10):  # si el puerto está ocupado, prueba el siguiente
        try:
            servidor = ThreadingHTTPServer((host, puerto + intento), Manejador)
            break
        except OSError:
            continue
    else:
        raise SystemExit(f"No hay puertos libres entre {puerto} y {puerto + 9}.")
    puerto = servidor.server_address[1]
    url = f"http://127.0.0.1:{puerto}/"
    print("\n  Estudio Generativo — texto, imagen y sonido en tu dispositivo")
    print(f"  Abre en el navegador: {url}")
    if red:
        print(f"  Desde otro aparato de tu Wi-Fi: http://{_ip_local()}:{puerto}/")
    print(f"  Lo generado se guarda en: {Manejador.carpeta}")
    print("  Para salir: Ctrl+C (o detén el programa)\n")
    if abrir:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor detenido.")
    finally:
        servidor.server_close()
