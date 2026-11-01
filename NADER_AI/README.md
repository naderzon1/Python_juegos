# NADER AI

Asistente de inteligencia artificial con interfaz web y narración de voz. La versión 0.1.0
prioriza el módulo de **texto a voz** y deja preparada la arquitectura para conversación con
modelos de lenguaje, imágenes, reconocimiento de voz y memoria.

## Estado de los módulos

| Módulo | Estado | Detalle |
|---|---|---|
| Voz Edge TTS | **Completo** | MP3 generado por el servicio de voz de Microsoft Edge. Requiere Internet: **no es local**. |
| Voz del navegador | **Completo** | `SpeechSynthesisUtterance`. Las voces dependen del navegador y del sistema operativo. |
| Dictado | **Completo (navegador)** | Reconocimiento de voz del navegador (Chrome/Edge). El navegador envía el audio a su propio servicio. |
| Conversación con IA (`/api/chat`) | **Preparado** | Proveedores `ollama` (local, gratis, sin clave) y `anthropic` (de pago); sin proveedor responde 503. No hay respuestas simuladas. |
| Imágenes (`/api/images`) | **Pendiente** | Solo la interfaz del servicio; responde 503 hasta conectar un proveedor. |
| Transcripción en servidor (`/api/transcribe`) | **Pendiente** | Recibe audio, responde 503 hasta conectar un proveedor. |
| Memoria | **Preparado (desactivado)** | Archivos JSON por conversación si `NADER_MEMORY_ENABLED=true`. |

## Estructura

```
NADER_AI/
├── server.py                    FastAPI: endpoints, validación, errores, archivos estáticos
├── requirements.txt
├── pytest.ini
├── .env.example                 configuración (sin claves reales)
├── static/
│   ├── index.html               interfaz
│   ├── styles.css
│   └── app.js                   motores de voz, estados, solicitudes a la API
├── services/
│   ├── config.py                lectura de variables de entorno y .env
│   ├── errors.py                errores controlados → respuestas HTTP claras
│   ├── speech_service.py        Edge TTS, voces permitidas, limpieza de archivos
│   ├── llm_service.py           proveedores de modelos de lenguaje
│   ├── image_service.py         interfaz para imágenes (pendiente)
│   ├── transcription_service.py interfaz para transcripción (pendiente)
│   └── memory_service.py        memoria opcional de conversaciones
├── tests/
│   ├── conftest.py              app de prueba con servicio de voz simulado
│   ├── test_health.py
│   ├── test_audio.py
│   └── test_integration_edge.py prueba opcional con el servicio real
└── generated_audio/             MP3 temporales (se borran solos)
```

## Instalación en Windows

Requisitos: Python 3.11 o superior (probado con Python 3.14.4) y conexión a Internet para Edge TTS.

Desde **PowerShell** o **CMD**, dentro de la carpeta `NADER_AI`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Ejecución

**Con doble clic:** abre `Iniciar NADER AI.bat` (o el acceso directo «NADER AI» del Escritorio).
La primera vez crea el entorno e instala las dependencias; después enciende el servidor y abre
el navegador. Si NADER AI ya estaba encendido, solo abre la página. Para apagarlo, cierra la
ventana negra «NADER AI» (queda minimizada en la barra de tareas).

**Desde la terminal:**

```powershell
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000
```

- Interfaz: http://127.0.0.1:8000
- Documentación de la API: http://127.0.0.1:8000/docs
- Estado: http://127.0.0.1:8000/api/health

También funciona `.\.venv\Scripts\python.exe server.py`, que arranca lo mismo.

**Detener el servidor:** pulsa `Ctrl+C` en la terminal donde se ejecuta.

**Uso:** escribe el texto, elige motor, voz y velocidad, y pulsa **Generar y reproducir**
(o `Ctrl+Enter`). Pausa, Reanudar y Detener controlan solo la reproducción; si pulsas Detener
mientras se genera el audio, la solicitud se cancela también en el servidor.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Las pruebas usan un servicio de voz simulado y no necesitan Internet. Para probar además el
servicio real de Edge (opcional, requiere Internet):

```powershell
$env:NADER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m pytest -m integration
```

En CMD: `set NADER_INTEGRATION=1` y luego el mismo comando de pytest.

## API

| Método y ruta | Uso |
|---|---|
| `GET /api/health` | estado del servidor, versión, módulos y límites |
| `GET /api/voices` | voces permitidas (`?verify=true` consulta a Edge cuáles existen hoy) |
| `POST /api/audio` | `{"text": "...", "voice": "es-CO-SalomeNeural", "rate": 0}` → `audio/mpeg` |
| `POST /api/chat` | `{"message": "...", "conversation_id": null}` → respuesta del modelo (503 si no hay proveedor) |
| `POST /api/images` | `{"prompt": "..."}` → imagen (503: pendiente) |
| `POST /api/transcribe` | cuerpo `audio/*` → texto (503: pendiente) |
| `DELETE /api/memory/{id}` | borra una conversación guardada |

Errores: siempre `{"error": {"code": "...", "message": "..."}}`, sin trazas internas.

| Código HTTP | Cuándo |
|---|---|
| 422 | texto vacío o demasiado largo, voz no permitida, velocidad fuera de -50..+50, JSON inválido |
| 502 | el servicio de voz o el modelo falló o no hay conexión con él |
| 503 | servidor ocupado (demasiadas generaciones simultáneas) o módulo sin configurar |
| 504 | el servicio de voz tardó más del tiempo límite |

## Configuración

Copia `.env.example` como `.env` y ajusta los valores. Las variables principales:

| Variable | Defecto | Uso |
|---|---|---|
| `NADER_MAX_TEXT_LENGTH` | 5000 | caracteres máximos por narración |
| `NADER_TTS_TIMEOUT_SECONDS` | 60 | tiempo límite del servicio de voz |
| `NADER_MAX_CONCURRENT_TTS` | 3 | generaciones simultáneas |
| `NADER_AUDIO_MAX_AGE_SECONDS` | 600 | antigüedad máxima de los MP3 temporales |
| `NADER_CORS_ORIGINS` | vacío | orígenes permitidos, solo si la interfaz está en otro dominio |
| `NADER_LLM_PROVIDER` | ninguno | `ollama` o `anthropic` para activar la conversación |
| `NADER_LLM_MODEL` | según proveedor | `llama3.2` con Ollama, `claude-opus-5-5` con Anthropic |
| `NADER_OLLAMA_URL` | http://127.0.0.1:11434 | dirección del servidor de Ollama |
| `NADER_MEMORY_ENABLED` | false | guardar conversaciones en `data/conversaciones/` |

### Activar la conversación con Ollama (local, gratis, sin clave)

1. Instala Ollama desde https://ollama.com/download (o `winget install Ollama.Ollama`) y ábrelo.
2. Descarga un modelo: `ollama pull llama3.2` (unos 2 GB).
3. En `.env`: `NADER_LLM_PROVIDER=ollama`. Para otro modelo, `NADER_LLM_MODEL=<nombre>`.
4. Reinicia el servidor. El botón «Preguntar a NADER AI» se activa solo.

Las respuestas se generan en tu equipo: nada sale a Internet y no hay costo. La velocidad
depende de tu procesador o tarjeta gráfica.

### Activar la conversación con Claude (opcional, de pago)

1. `.\.venv\Scripts\python.exe -m pip install anthropic`
2. En `.env`: `NADER_LLM_PROVIDER=anthropic` y `ANTHROPIC_API_KEY=` con tu clave de la API de Claude.
3. Reinicia el servidor. El botón «Preguntar a NADER AI» se activa solo.

El uso se cobra en tu cuenta de la API de Claude, aparte de cualquier suscripción. Este
proveedor está implementado pero **no se ha probado con una clave real**.

Para agregar otro proveedor, crea una clase con el método
`reply` en `services/llm_service.py` y regístrala en `build_llm_provider`. La interfaz no cambia.

## Privacidad

- El texto que narras con Edge TTS se envía al servicio de voz de Microsoft.
- El servidor no registra los textos: los registros solo guardan la voz, la longitud y la duración.
- Los MP3 se borran al entregarse; los que queden por un fallo se eliminan a los 10 minutos.
- La memoria de conversaciones está desactivada por defecto. Si la activas, se guarda en
  `data/conversaciones/`; bórrala con `DELETE /api/memory/{id}` o eliminando esa carpeta.

## Seguridad

- Este es un **servidor de desarrollo**: escúchalo solo en `127.0.0.1` y no lo expongas directamente a Internet.
- No guardes claves en el código: van en `.env`, que está en `.gitignore`.
- Solo se aceptan las cuatro voces configuradas y los archivos de `static/`; `generated_audio/` no es accesible desde el navegador.

## Problemas comunes

| Síntoma | Solución |
|---|---|
| `"python" no se reconoce` | Instala Python desde python.org y marca «Add python.exe to PATH». |
| `No module named uvicorn` | Usa `.\.venv\Scripts\python.exe` (el del entorno virtual) o repite la instalación. |
| `[Errno 10048]` / puerto en uso | Otro programa usa el 8000: cambia a `--port 8001`. |
| «No se pudo conectar con el servicio de voz de Edge» | Revisa la conexión a Internet, el firewall o el proxy. Mientras tanto usa «Voz del navegador». |
| La lista «Voz del navegador» está vacía | Instala voces en español en Windows (Configuración → Hora e idioma → Voz) o usa Edge/Chrome. |
| El audio no arranca solo | Algunos navegadores bloquean la reproducción automática: pulsa ▶ en el reproductor. |
| `pip` falla con errores SSL | Repite el comando; si persiste, revisa el antivirus o el proxy de la red. |

## Verificación realizada (16/10/2026)

- `pytest`: 26 pruebas pasan, 2 de integración omitidas por defecto.
- `pytest -m integration` con Internet: 2 pruebas pasan (MP3 real y las 4 voces existen en Edge).
- Servidor iniciado con el comando de uvicorn de este README: la interfaz carga sin errores de rutas,
  genera y reproduce el MP3, y pausa, reanuda y detiene. Detener durante la generación cancela la tarea
  en el servidor. La voz del navegador narra y se detiene. Diseño revisado a 375 px de ancho.
- No probado: conversación con un proveedor real de IA (no hay clave configurada), y el dictado
  (requiere micrófono).
