"""Servidor HTTP. Solo libreria estandar: no requiere instalar nada."""
from __future__ import annotations

import json
import mimetypes
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from aplicacion.casos_uso.contexto import Contexto
from aplicacion.casos_uso.registro import ErrorValidacion
from api.rutas import PREFIJO, Api, Respuesta
from infraestructura.archivos.parseo import ErrorArchivo
from infraestructura.trabajos.cola import ColaReprocesos

RAIZ_WEB = Path(__file__).resolve().parents[1] / "web"
LIMITE_CUERPO = 64 * 1024 * 1024


def construir(ruta_bd: str) -> tuple[Api, ColaReprocesos]:
    ctx = Contexto.abrir(ruta_bd)
    cola = ColaReprocesos(ruta_bd)
    return Api(ctx, cola), cola


class Manejador(BaseHTTPRequestHandler):
    api: Api = None  # inyectado en crear_servidor
    server_version = "GOI/1.0"

    def log_message(self, formato: str, *args) -> None:
        if "/api/" in (args[0] if args else ""):
            super().log_message(formato, *args)

    # --- verbos -----------------------------------------------------------
    def do_GET(self) -> None:
        self._manejar("GET")

    def do_POST(self) -> None:
        self._manejar("POST")

    def do_PUT(self) -> None:
        self._manejar("PUT")

    def do_DELETE(self) -> None:
        self._manejar("DELETE")

    # --- nucleo -----------------------------------------------------------
    def _manejar(self, metodo: str) -> None:
        url = urlparse(self.path)
        camino = unquote(url.path)
        consulta = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if camino.startswith(PREFIJO):
                longitud = int(self.headers.get("Content-Length") or 0)
                if longitud > LIMITE_CUERPO:
                    return self._error(413, "El archivo supera el limite de 64 MB.")
                cuerpo = self.rfile.read(longitud) if longitud else b""
                r = self.api.despachar(metodo, camino, consulta, cuerpo, dict(self.headers))
                if r is None:
                    return self._error(404, f"Ruta no encontrada: {metodo} {camino}")
                return self._responder(r)
            if metodo == "GET":
                return self._estatico(camino)
            return self._error(405, f"Metodo no permitido: {metodo}")
        except ErrorValidacion as e:
            self._error(422, e.mensaje, campo=e.campo)
        except ErrorArchivo as e:
            self._error(422, str(e))
        except PermissionError as e:
            self._error(403, str(e))
        except (ValueError, KeyError, TypeError) as e:
            self._error(400, f"{type(e).__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._error(500, f"{type(e).__name__}: {e}")

    def _responder(self, r: Respuesta) -> None:
        if r.binario is not None:
            datos = r.binario
        else:
            datos = json.dumps(r.cuerpo, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(r.estado)
        self.send_header("Content-Type", r.tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        for k, v in r.cabeceras.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(datos)

    def _error(self, codigo: int, mensaje: str, **extra) -> None:
        datos = json.dumps({"error": mensaje, **extra}, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _estatico(self, camino: str) -> None:
        rel = camino.lstrip("/") or "index.html"
        destino = (RAIZ_WEB / rel).resolve()
        if not str(destino).startswith(str(RAIZ_WEB.resolve())):
            return self._error(403, "Ruta fuera del directorio web.")
        if destino.is_dir():
            destino = destino / "index.html"
        if not destino.exists():
            destino = RAIZ_WEB / "index.html"
        tipo = mimetypes.guess_type(str(destino))[0] or "application/octet-stream"
        if destino.suffix in (".js", ".mjs"):
            tipo = "text/javascript; charset=utf-8"
        if destino.suffix == ".css":
            tipo = "text/css; charset=utf-8"
        datos = destino.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos)


def crear_servidor(ruta_bd: str, puerto: int = 8765,
                   host: str = "127.0.0.1") -> tuple[ThreadingHTTPServer, Api]:
    api, _cola = construir(ruta_bd)
    manejador = type("ManejadorConfigurado", (Manejador,), {"api": api})
    servidor = ThreadingHTTPServer((host, puerto), manejador)
    return servidor, api
