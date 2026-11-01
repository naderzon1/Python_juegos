"""NADER AI: servidor FastAPI.

Ejecutar:
    .\\.venv\\Scripts\\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000

Servidor de desarrollo: no lo expongas directamente a Internet.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.background import BackgroundTask

from services.config import APP_NAME, APP_VERSION, RAIZ, Settings
from services.errors import AppError, ProviderTimeout, ServerBusy
from services.image_service import build_image_provider
from services.llm_service import ChatMessage, build_llm_provider
from services.memory_service import build_store
from services.speech_service import (
    DEFAULT_VOICE,
    VOICE_IDS,
    VOICES,
    EdgeSpeechService,
    SpeechService,
    available_edge_voices,
    cleanup_old_audio,
    new_audio_path,
    remove_quietly,
)
from services.transcription_service import build_transcription_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("nader")

STATIC_DIR = RAIZ / "static"
MAX_AUDIO_UPLOAD = 10 * 1024 * 1024  # 10 MB para /api/transcribe


# ---------- Modelos de entrada ----------
class AudioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    voice: str = DEFAULT_VOICE
    rate: int = Field(0, ge=-50, le=50)

    @field_validator("text")
    @classmethod
    def texto_no_vacio(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("El texto está vacío. Escribe algo para narrar.")
        return valor

    @field_validator("voice")
    @classmethod
    def voz_permitida(cls, valor: str) -> str:
        if valor not in VOICE_IDS:
            raise ValueError("Voz no disponible. Elige una de las voces de la lista.")
        return valor


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    conversation_id: str | None = None

    @field_validator("message")
    @classmethod
    def mensaje_no_vacio(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("El mensaje está vacío.")
        return valor


class ImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=2000)


# Mensajes en español para los errores de validación de cada campo
_MENSAJES_CAMPO = {
    "text": ("texto_vacio", "El texto es obligatorio."),
    "voice": ("voz_no_disponible", "Voz no disponible. Elige una de las voces de la lista."),
    "rate": ("velocidad_fuera_de_rango", "La velocidad debe ser un número entero entre -50 y +50."),
    "message": ("mensaje_vacio", "El mensaje es obligatorio."),
    "prompt": ("descripcion_invalida", "La descripción de la imagen debe tener entre 1 y 2000 caracteres."),
}


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


# ---------- Aplicación ----------
def create_app(settings: Settings | None = None, speech: SpeechService | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        cleanup_old_audio(settings.audio_dir, settings.audio_max_age_seconds)

        async def limpieza_periodica():
            while True:
                await asyncio.sleep(max(60, settings.audio_max_age_seconds // 2))
                cleanup_old_audio(settings.audio_dir, settings.audio_max_age_seconds)

        tarea = asyncio.create_task(limpieza_periodica())
        log.info("%s %s listo. Voz: Edge TTS (servicio externo, requiere Internet).", APP_NAME, APP_VERSION)
        try:
            yield
        finally:
            tarea.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tarea

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="API de NADER AI: síntesis de voz y módulos preparados para IA generativa.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.speech = speech or EdgeSpeechService()
    app.state.tts_slots = asyncio.Semaphore(settings.max_concurrent_tts)
    app.state.llm = build_llm_provider(settings.llm_provider, settings.llm_model, settings.ollama_url)
    app.state.images = build_image_provider(settings.image_provider)
    app.state.transcription = build_transcription_provider(settings.transcription_provider)
    app.state.memory = build_store(settings.memory_enabled, settings.memory_dir)

    if settings.cors_origins:  # solo si la interfaz se sirve desde otro origen
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type"],
        )

    # ---------- Manejo centralizado de errores ----------
    @app.exception_handler(AppError)
    async def manejar_app_error(_: Request, error: AppError):
        return _error(error.status_code, error.code, error.message)

    @app.exception_handler(RequestValidationError)
    async def manejar_validacion(_: Request, error: RequestValidationError):
        primero = error.errors()[0] if error.errors() else {}
        loc = primero.get("loc", ())
        campo = loc[-1] if loc else ""
        if primero.get("type") == "json_invalid":
            return _error(422, "solicitud_invalida", "El cuerpo de la solicitud no es JSON válido.")
        if primero.get("type") == "extra_forbidden":
            return _error(422, "campo_desconocido", f"Campo no permitido: {campo}.")
        codigo, mensaje = _MENSAJES_CAMPO.get(campo, ("solicitud_invalida", "La solicitud no es válida."))
        if primero.get("type") == "value_error":  # mensajes de nuestros validadores
            mensaje = str(primero.get("msg", mensaje)).removeprefix("Value error, ")
        return _error(422, codigo, mensaje)

    @app.exception_handler(Exception)
    async def manejar_inesperado(_: Request, error: Exception):
        log.exception("Error no controlado: %s", error.__class__.__name__)
        return _error(500, "error_interno", "Ocurrió un error interno. Intenta de nuevo.")

    # ---------- Endpoints ----------
    @app.get("/api/health", tags=["estado"])
    async def health():
        return {
            "status": "ok",
            "app": APP_NAME,
            "version": APP_VERSION,
            "modules": {
                "voz_edge": {"estado": "completo", "requiere_internet": True},
                "voz_navegador": {"estado": "completo", "nota": "depende del navegador y del sistema operativo"},
                "llm": {
                    "estado": "configurado" if app.state.llm.configured else "no_configurado",
                    "proveedor": app.state.llm.name,
                },
                "imagenes": {"estado": "configurado" if app.state.images.configured else "pendiente"},
                "transcripcion": {"estado": "configurado" if app.state.transcription.configured else "pendiente"},
                "memoria": {"estado": "activada" if app.state.memory.enabled else "desactivada"},
            },
            "limits": {"max_text_length": settings.max_text_length, "rate_min": -50, "rate_max": 50},
        }

    @app.get("/api/voices", tags=["voz"])
    async def voices(verify: bool = False):
        disponibles = await available_edge_voices() if verify else None
        return {
            "default": DEFAULT_VOICE,
            "verified": disponibles is not None,
            "voices": [
                {
                    "id": v.id,
                    "name": v.name,
                    "locale": v.locale,
                    "gender": v.gender,
                    **({"available": v.id in disponibles} if disponibles is not None else {}),
                }
                for v in VOICES
            ],
        }

    @app.post(
        "/api/audio",
        tags=["voz"],
        response_class=Response,
        responses={200: {"content": {"audio/mpeg": {}}, "description": "Archivo MP3"}},
    )
    async def audio(datos: AudioRequest, request: Request):
        if len(datos.text) > settings.max_text_length:
            raise AppError(
                f"El texto supera el máximo de {settings.max_text_length} caracteres.",
                code="texto_demasiado_largo",
                status_code=422,
            )
        cleanup_old_audio(settings.audio_dir, settings.audio_max_age_seconds)

        try:
            await asyncio.wait_for(app.state.tts_slots.acquire(), settings.queue_wait_seconds)
        except TimeoutError:
            raise ServerBusy("Hay demasiadas solicitudes de audio en curso. Intenta de nuevo en unos segundos.")

        destino = new_audio_path(settings.audio_dir)
        inicio = time.perf_counter()
        try:
            await _sintetizar_vigilando(app.state.speech, datos, destino, request, settings.tts_timeout_seconds)
        except BaseException:
            remove_quietly(destino)
            raise
        finally:
            app.state.tts_slots.release()

        if not destino.is_file():  # el navegador canceló la solicitud
            return Response(status_code=499)
        # Nunca se registra el texto: solo su longitud y la voz.
        log.info(
            "Audio generado | voz=%s | %d caracteres | %.2fs",
            datos.voice, len(datos.text), time.perf_counter() - inicio,
        )
        return FileResponse(
            destino,
            media_type="audio/mpeg",
            filename="nader-ai.mp3",
            headers={"Cache-Control": "no-store"},
            background=BackgroundTask(remove_quietly, destino),
        )

    @app.post("/api/chat", tags=["ia"])
    async def chat(datos: ChatRequest):
        if len(datos.message) > settings.llm_max_input:
            raise AppError(
                f"El mensaje supera el máximo de {settings.llm_max_input} caracteres.",
                code="mensaje_demasiado_largo",
                status_code=422,
            )
        memoria = app.state.memory
        conversacion = datos.conversation_id or memoria.new_id()
        historial = memoria.load(conversacion) + [ChatMessage("user", datos.message)]
        respuesta = await app.state.llm.reply(historial)
        memoria.save(conversacion, historial + [ChatMessage("assistant", respuesta)])
        return {"reply": respuesta, "conversation_id": conversacion, "provider": app.state.llm.name}

    @app.post("/api/images", tags=["ia"])
    async def images(datos: ImageRequest):
        imagen = await app.state.images.generate(datos.prompt)
        return Response(imagen.data, media_type=imagen.mime_type, headers={"Cache-Control": "no-store"})

    @app.post("/api/transcribe", tags=["ia"])
    async def transcribe(request: Request):
        tipo = request.headers.get("content-type", "")
        if not tipo.startswith("audio/"):
            raise AppError("Envía el audio con un Content-Type audio/*.", code="tipo_no_admitido", status_code=415)
        if not app.state.transcription.configured:  # no se lee el audio si no hay quién lo procese
            await app.state.transcription.transcribe(b"", tipo)
        cuerpo = bytearray()
        async for parte in request.stream():
            cuerpo.extend(parte)
            if len(cuerpo) > MAX_AUDIO_UPLOAD:
                raise AppError("El audio supera 10 MB.", code="audio_demasiado_grande", status_code=413)
        return {"text": await app.state.transcription.transcribe(bytes(cuerpo), tipo)}

    @app.delete("/api/memory/{conversation_id}", tags=["ia"])
    async def borrar_memoria(conversation_id: str):
        return {"deleted": app.state.memory.delete(conversation_id), "memoria": app.state.memory.enabled}

    # ---------- Interfaz ----------
    @app.get("/", include_in_schema=False)
    async def inicio():
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


async def _sintetizar_vigilando(
    speech: SpeechService, datos: AudioRequest, destino: Path, request: Request, timeout: int
) -> None:
    """Genera el audio y lo cancela si el navegador cierra la conexión o se agota el tiempo."""

    async def esperar_desconexion():
        while not await request.is_disconnected():
            await asyncio.sleep(0.25)

    tarea = asyncio.create_task(speech.synthesize(datos.text, datos.voice, datos.rate, destino))
    vigia = asyncio.create_task(esperar_desconexion())
    try:
        hechas, _ = await asyncio.wait({tarea, vigia}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
    finally:
        vigia.cancel()
    if tarea in hechas:
        tarea.result()  # propaga ProviderError
        return
    tarea.cancel()
    await asyncio.gather(tarea, return_exceptions=True)
    remove_quietly(destino)
    if vigia in hechas:
        log.info("Solicitud de audio cancelada por el navegador")
        return
    raise ProviderTimeout("El servicio de voz tardó demasiado en responder. Intenta con un texto más corto.")


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000)
