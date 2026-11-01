"""Generación de imágenes (integración pendiente).

Solo existe la interfaz del servicio. Mientras NADER_IMAGE_PROVIDER sea "ninguno",
/api/images responde 503 "no configurado": no se devuelven imágenes de relleno.
Para integrar un proveedor, crea una clase con el método `generate` y regístrala en
`build_image_provider`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .errors import NotConfigured


@dataclass(frozen=True)
class GeneratedImage:
    mime_type: str  # "image/png", "image/jpeg"…
    data: bytes


class ImageProvider(Protocol):
    name: str
    configured: bool

    async def generate(self, prompt: str) -> GeneratedImage:
        ...


class NoImageProvider:
    name = "ninguno"
    configured = False

    async def generate(self, prompt: str) -> GeneratedImage:
        raise NotConfigured("No hay un proveedor de imágenes configurado (NADER_IMAGE_PROVIDER).")


def build_image_provider(provider: str) -> ImageProvider:
    # Aquí se agregarán los proveedores reales cuando se integren.
    return NoImageProvider()
