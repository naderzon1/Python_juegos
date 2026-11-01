"""Prisma Generativo: servidor local.

Sirve la página (static/index.html) y hace de puente con la API de Claude,
así la clave de API se queda en tu computador y nunca llega al navegador.

Ejecuta:  python server.py   y abre http://localhost:8765
"""

from __future__ import annotations

import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

RAIZ = Path(__file__).resolve().parent
ESTATICOS = RAIZ / "static"


def cargar_env(ruta: Path) -> None:
    """Lee un archivo .env sencillo (CLAVE=valor) sin pisar variables ya definidas."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave, valor = clave.strip(), valor.strip().strip('"').strip("'")
        if clave and valor and clave not in os.environ:
            os.environ[clave] = valor


cargar_env(RAIZ / ".env")

MODELO = os.environ.get("PRISMA_MODELO", "claude-opus-5-5")
PUERTO = int(os.environ.get("PRISMA_PUERTO", "8765"))
HOSTS_PERMITIDOS = {f"localhost:{PUERTO}", f"127.0.0.1:{PUERTO}"}

# "rapido" = plan semántico (JSON corto); "normal" = texto e ilustración SVG
ESFUERZO = {"rapido": "low", "normal": "medium"}
MAX_TOKENS = {"rapido": 8000, "normal": 32000}
MAX_PROMPT = 200_000  # caracteres

# Modelos que aceptan el respaldo automático del servidor cuando un filtro de
# seguridad rechaza la petición (fallbacks="default").
CON_RESPALDO = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

TIPOS = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

try:
    cliente: anthropic.Anthropic | None = anthropic.Anthropic()
except Exception as error:  # sin credenciales en algunas versiones del SDK
    print(f"[prisma] No se pudo crear el cliente de Claude: {error}")
    cliente = None

# El SDK crea el cliente aunque no haya credenciales y solo falla al llamar a la API;
# sin ninguna, la página debe pasar a modo local en lugar de fallar en cada generación.
if cliente is not None and not (cliente.api_key or cliente.auth_token or cliente.credentials):
    print("[prisma] Falta ANTHROPIC_API_KEY (.env): la página funcionará en modo local.")
    cliente = None


def codigo_de_error(error: Exception) -> tuple[str, str]:
    """Traduce las excepciones del SDK a los códigos que entiende la página."""
    if isinstance(error, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return "auth", "La clave de API no es válida o no tiene permiso."
    if isinstance(error, anthropic.RateLimitError):
        return "rate_limited", "Límite de solicitudes alcanzado."
    if isinstance(error, anthropic.BadRequestError):
        return "invalid_request", str(error)
    if isinstance(error, anthropic.APIStatusError):
        return "upstream_error", f"Error {error.status_code} de la API."
    if isinstance(error, anthropic.APIConnectionError):
        return "upstream_error", "No hay conexión con la API de Claude."
    if "auth" in str(error).lower():
        return "auth", "No se encontró la clave de API (ANTHROPIC_API_KEY)."
    return "upstream_error", str(error)


class Manejador(BaseHTTPRequestHandler):
    server_version = "Prisma/1.0"

    # ---------- utilidades ----------
    def host_valido(self) -> bool:
        # Evita que otra web abierta en tu navegador use tu clave a través de localhost.
        if self.headers.get("Host", "") not in HOSTS_PERMITIDOS:
            return False
        origen = self.headers.get("Origin")
        return origen is None or origen.split("//", 1)[-1] in HOSTS_PERMITIDOS

    def responder_json(self, estado: int, datos: dict) -> None:
        cuerpo = json.dumps(datos).encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def enviar(self, evento: dict) -> None:
        self.wfile.write((json.dumps(evento, ensure_ascii=False) + "\n").encode("utf-8"))
        self.wfile.flush()

    def log_message(self, formato: str, *args) -> None:
        print(f"[prisma] {self.address_string()} {formato % args}")

    # ---------- rutas ----------
    def do_GET(self) -> None:
        if not self.host_valido():
            self.send_error(403)
            return
        ruta = self.path.split("?", 1)[0]
        if ruta == "/api/estado":
            self.responder_json(200, {"claude": cliente is not None, "modelo": MODELO})
            return
        archivo = (ESTATICOS / ("index.html" if ruta == "/" else ruta.lstrip("/"))).resolve()
        if not archivo.is_relative_to(ESTATICOS) or not archivo.is_file():
            self.send_error(404)
            return
        cuerpo = archivo.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", TIPOS.get(archivo.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_POST(self) -> None:
        if self.path != "/api/generar" or not self.host_valido():
            self.send_error(403)
            return
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            self.send_error(415)
            return
        try:
            largo = int(self.headers.get("Content-Length", "0"))
            datos = json.loads(self.rfile.read(largo) or b"{}")
            prompt = str(datos.get("prompt", "")).strip()
            nivel = datos.get("nivel") if datos.get("nivel") in ESFUERZO else "normal"
        except (ValueError, json.JSONDecodeError):
            self.responder_json(400, {"error": "JSON inválido"})
            return
        if not prompt or len(prompt) > MAX_PROMPT:
            self.responder_json(400, {"error": "Instrucción vacía o demasiado larga"})
            return

        # Respuesta en streaming: una línea JSON por evento (NDJSON).
        # HTTP/1.0 sin Content-Length: el fin de la conexión marca el fin del cuerpo.
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        if cliente is None:
            self.enviar({"t": "error", "code": "auth", "message": "Cliente de Claude sin configurar."})
            return
        try:
            self.generar(prompt, nivel)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # La página pulsó Detener: al salir del `with` se cierra el stream y deja de cobrarse.
            print("[prisma] solicitud cancelada por el navegador")
        except Exception as error:
            codigo, mensaje = codigo_de_error(error)
            print(f"[prisma] error: {codigo} · {error}")
            try:
                self.enviar({"t": "error", "code": codigo, "message": mensaje})
            except OSError:
                pass

    def generar(self, prompt: str, nivel: str) -> None:
        parametros: dict = {
            "model": MODELO,
            "max_tokens": MAX_TOKENS[nivel],
            "output_config": {"effort": ESFUERZO[nivel]},
            "messages": [{"role": "user", "content": prompt}],
        }
        if MODELO in CON_RESPALDO:
            parametros["betas"] = ["server-side-fallback-2026-07-01"]
            parametros["fallbacks"] = "default"
        with cliente.beta.messages.stream(**parametros) as stream:
            for texto in stream.text_stream:
                self.enviar({"t": "delta", "text": texto})
            final = stream.get_final_message()
        if final.stop_reason == "refusal":
            self.enviar({"t": "error", "code": "refused", "message": "Claude rechazó la instrucción."})
        else:
            self.enviar({"t": "fin", "stop": final.stop_reason, "modelo": final.model})


def main() -> None:
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    url = f"http://localhost:{PUERTO}"
    print(f"[prisma] Modelo: {MODELO}")
    print(f"[prisma] Abierto en {url}  (Ctrl+C para detener)")
    if os.environ.get("PRISMA_SIN_NAVEGADOR") != "1":
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n[prisma] Servidor detenido.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
