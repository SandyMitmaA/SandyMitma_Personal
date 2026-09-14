@echo off
REM Lanzador para Windows: levanta el servidor local y abre el navegador.
REM El sistema solo necesita servirse por http:// (el navegador bloquea los
REM modulos ES abiertos con doble clic sobre el archivo). Sirve cualquier
REM servidor estatico, asi que se usa Node si esta instalado y Python si no.

setlocal
cd /d "%~dp0"
set PUERTO=8123

where node >nul 2>nul
if %errorlevel%==0 (
  echo Iniciando el sistema con Node en http://localhost:%PUERTO%
  start "Sistema de Valorizacion - servidor" /min node herramientas\servidor.mjs %PUERTO%
  goto :abrir
)

where python >nul 2>nul
if %errorlevel%==0 (
  echo Node no esta instalado. Se usa Python, que tambien alcanza.
  start "Sistema de Valorizacion - servidor" /min python -m http.server %PUERTO%
  goto :abrir
)

echo.
echo No se encontro ni Node ni Python en esta computadora.
echo.
echo Opciones:
echo   1. Instalar Node desde https://nodejs.org (version LTS)
echo   2. Abrir la carpeta en VS Code e instalar la extension "Live Server"
echo   3. Usar la version publicada en linea, que no necesita instalar nada
echo.
pause
exit /b 1

:abrir
timeout /t 2 >nul
start "" http://localhost:%PUERTO%
echo.
echo Listo. El sistema quedo abierto en http://localhost:%PUERTO%
echo Para detenerlo, cierre la ventana titulada "Sistema de Valorizacion - servidor".
echo.
timeout /t 5 >nul
