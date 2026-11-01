@echo off
rem NADER AI - lanzador de doble clic.
rem Enciende el servidor (o lo reutiliza si ya esta encendido) y abre la interfaz en el navegador.
rem Cerrar esta ventana apaga NADER AI.
setlocal
title NADER AI
cd /d "%~dp0"
if "%NADER_PORT%"=="" set "NADER_PORT=8000"
set "NADER_URL=http://127.0.0.1:%NADER_PORT%"

rem --- Primera vez: crear el entorno e instalar dependencias ---
if not exist ".venv\Scripts\python.exe" (
    echo Preparando NADER AI por primera vez. Esto tarda unos minutos...
    python -m venv .venv || goto :sin_python
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error_instalacion
)

rem --- Si ya esta encendido, solo abrir la interfaz ---
powershell -NoProfile -Command "try { Invoke-WebRequest '%NADER_URL%/api/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if not errorlevel 1 (
    if not "%NADER_NO_BROWSER%"=="1" start "" "%NADER_URL%"
    exit /b 0
)

rem --- Abrir el navegador cuando el servidor responda ---
if not "%NADER_NO_BROWSER%"=="1" start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for ($i = 0; $i -lt 60; $i++) { try { Invoke-WebRequest '%NADER_URL%/api/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; Start-Process '%NADER_URL%'; break } catch { Start-Sleep -Milliseconds 500 } }"

echo.
echo   NADER AI esta encendido en %NADER_URL%
echo   No cierres esta ventana mientras lo uses. Cerrarla apaga NADER AI.
echo.
".venv\Scripts\python.exe" -m uvicorn server:app --host 127.0.0.1 --port %NADER_PORT%
echo.
echo NADER AI se detuvo.
pause
exit /b 0

:sin_python
echo.
echo No se encontro Python. Instalalo desde https://www.python.org marcando "Add python.exe to PATH".
pause
exit /b 1

:error_instalacion
echo.
echo No se pudieron instalar las dependencias. Revisa tu conexion a Internet y vuelve a intentarlo.
pause
exit /b 1
