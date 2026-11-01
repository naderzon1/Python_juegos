"""Errores de la aplicación con código HTTP y mensaje apto para el usuario final."""

from __future__ import annotations


class AppError(Exception):
    """Error controlado: su mensaje se muestra tal cual en la interfaz."""

    status_code = 500
    code = "error_interno"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class ProviderError(AppError):
    """Falló un servicio externo (voz, modelo de lenguaje, imágenes)."""

    status_code = 502
    code = "error_proveedor"


class ProviderTimeout(AppError):
    status_code = 504
    code = "tiempo_agotado"


class ServerBusy(AppError):
    status_code = 503
    code = "servidor_ocupado"


class NotConfigured(AppError):
    """El módulo existe pero no hay un proveedor configurado: no se simula una respuesta."""

    status_code = 503
    code = "no_configurado"
