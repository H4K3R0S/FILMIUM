@echo off
REM FILMIUM celija -- univerzalni pokretac (Windows ulaz).
REM Prepozna OS: ako NIJE Windows, predaje Linux pokretacu start.sh i gasi se.
cd /d "%~dp0"

if not "%OS%"=="Windows_NT" (
  echo Nije Windows -> predajem Linux pokretacu start.sh i gasim se.
  bash "%~dp0start.sh"
  exit /b 0
)

REM Windows: koristi Windows .venv i pokrece prozor aplikacije (FILMIUM.exe).
if not exist ".venv\Scripts\python.exe" (
  echo Celija nema svoje Windows Python okruzenje (.venv).
  echo Pokreni u CORE repou: build_cell.py filmium "%~dp0." 4801 --update
  pause
  exit /b 1
)
start "" "%~dp0FILMIUM.exe"
