# Prisma Generativo

Escribe una instrucción en el campo en blanco y Prisma devuelve **texto, imagen y audio**.
Un servidor Python local (`server.py`) sirve la página y llama a la API de Claude; la clave de API nunca sale de tu computador.

```
prisma_generativo/
├── server.py          servidor local + puente con la API de Claude
├── static/index.html  la interfaz (flujo de datos, texto, imagen, audio)
├── requirements.txt
├── .env.example       plantilla de configuración
└── .vscode/           intérprete y botón F5 para VS Code
```

## Flujo de datos

| Etapa | Dónde corre | Qué hace |
|---|---|---|
| 01 Análisis léxico | navegador | tokens, frecuencias, polaridad, energía y semilla (FNV-1a) |
| 02 Plan semántico | Claude (esfuerzo bajo) | JSON con título, idioma, tono, paleta y parámetros musicales |
| 03 Texto | Claude (streaming) | respuesta escrita para leerse en voz alta |
| 04 Imagen | Claude + navegador | ilustración SVG + campo de flujo con ruido de valor |
| 05 Audio | navegador | melodía por cadena de Markov sobre la escala, síntesis Web Audio y narración con la voz del sistema |

## Ejecutar en Visual Studio Code

1. Abre la carpeta `prisma_generativo` en VS Code (**Archivo → Abrir carpeta**).
2. Instala la extensión **Python** de Microsoft si VS Code la sugiere.
3. Crea tu archivo `.env` a partir de la plantilla y pega tu clave de API:
   ```powershell
   Copy-Item .env.example .env
   ```
   Luego edita `.env` y completa `ANTHROPIC_API_KEY=`.
4. Si la carpeta `.venv` no existe, créala e instala la dependencia desde la terminal de VS Code:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
5. Pulsa **F5** (configuración «Prisma: iniciar servidor»), o en la terminal:
   ```powershell
   .\.venv\Scripts\python.exe server.py
   ```
6. Se abre `http://localhost:8765` en tu navegador. Escribe y pulsa **Enter**.

Para detenerlo: **Shift+F5** en VS Code o **Ctrl+C** en la terminal.

## Configuración (`.env`)

| Variable | Por defecto | Uso |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | tu clave de la API de Claude (obligatoria para texto e ilustración) |
| `PRISMA_MODELO` | `claude-opus-5-5` | modelo que responde |
| `PRISMA_PUERTO` | `8765` | puerto local |
| `PRISMA_SIN_NAVEGADOR` | — | ponlo en `1` para no abrir el navegador al iniciar |

Sin clave, la página funciona en **modo local**: campo de flujo, música y un resumen del análisis.

## Notas

- Cada generación hace 3 llamadas a la API (plan, texto, ilustración) y se cobra en tu cuenta de la API de Claude.
- Si un filtro de seguridad rechaza la petición, el servidor activa el respaldo automático (`fallbacks: "default"`) y otro modelo termina la respuesta.
- El servidor solo escucha en `127.0.0.1` y rechaza peticiones de otros sitios web.
- La narración usa las voces instaladas en Windows o en el navegador; Edge y Chrome traen voces en español.
