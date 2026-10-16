@echo off
rem GALACTIC DOMINION 3D - lanzador para Windows.
rem La primera vez crea el entorno virtual e instala las dependencias.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creando el entorno virtual...
    py -3.13 -m venv .venv 2>nul || py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo No se encontro Python 3.11-3.13. Instalalo desde https://www.python.org/ y vuelve a intentarlo.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
