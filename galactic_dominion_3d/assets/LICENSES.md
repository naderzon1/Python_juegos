# Recursos y licencias

GALACTIC DOMINION 3D no incluye recursos de terceros. Todo el contenido audiovisual se genera con
el código del propio proyecto:

| Recurso | Origen | Dónde |
|---|---|---|
| Modelos 3D (naves, jefes, estaciones, carguero, portal, asteroides, restos) | Procedurales, código original | `game/graphics/models.py`, `game/graphics/procedural.py` |
| Texturas (planetas, anillos, nebulosas, paneles del casco, roca, sprites) | Procedurales con NumPy, código original | `game/graphics/textures.py` |
| Shaders GLSL (bloom, mapeo de tonos, atmósferas, escudos, portal, polvo, salto) | Código original | `assets/shaders/` |
| Efectos de sonido y música | Síntesis con NumPy, código original; se generan en `assets/audio/generated/` la primera vez | `game/audio/synth.py` |
| Fuente de texto | La del sistema operativo (no se redistribuye) o la interna de Panda3D | `game/ui/theme.py` |

Bibliotecas: Panda3D (licencia BSD modificada), NumPy (licencia BSD), pytest (licencia MIT).

Los sonidos son síntesis sencillas pensadas como recursos provisionales. Para sustituirlos por
grabaciones con licencia compatible basta con dejar un WAV con el mismo nombre en
`assets/audio/generated/` (y no borrar el archivo `VERSION`, o el juego los regenerará).
Si añades modelos o fuentes externas, anota aquí su autor y licencia.
