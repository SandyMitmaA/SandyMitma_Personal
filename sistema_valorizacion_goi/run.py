#!/usr/bin/env python3
"""Sistema de Valorizacion Interno - GOI.

Arranque local. Solo requiere Python 3.9 o superior: sin pip, sin npm, sin
servidor de base de datos. La base es un archivo SQLite que puedes abrir con
cualquier visor (por ejemplo DB Browser for SQLite) sin instalar el sistema.

    python3 run.py                      arranca en http://127.0.0.1:8765
    python3 run.py --puerto 9000        otro puerto
    python3 run.py --bd cartera.db      otra base
    python3 run.py --sembrar            carga los datos de ejemplo de la Parte IV
    python3 run.py --reiniciar          borra la base y vuelve a crearla
    python3 run.py --pruebas            corre la bateria de pruebas
"""
from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

BD_POR_DEFECTO = RAIZ / "datos" / "valorizacion_goi.sqlite"


def main() -> int:
    p = argparse.ArgumentParser(description="Sistema de Valorizacion Interno - GOI")
    p.add_argument("--puerto", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--bd", default=str(BD_POR_DEFECTO))
    p.add_argument("--sembrar", action="store_true",
                   help="carga los datos de ejemplo de la Parte IV")
    p.add_argument("--reiniciar", action="store_true", help="borra la base antes de arrancar")
    p.add_argument("--sin-navegador", action="store_true")
    p.add_argument("--pruebas", action="store_true", help="ejecuta las pruebas y sale")
    args = p.parse_args()

    if sys.version_info < (3, 9):
        print("Se requiere Python 3.9 o superior.", file=sys.stderr)
        return 1

    if args.pruebas:
        import unittest

        cargador = unittest.TestLoader()
        suite = cargador.discover(str(RAIZ / "tests"), top_level_dir=str(RAIZ))
        resultado = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if resultado.wasSuccessful() else 1

    ruta = Path(args.bd)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if args.reiniciar:
        for sufijo in ("", "-wal", "-shm"):
            f = Path(str(ruta) + sufijo)
            if f.exists():
                f.unlink()
        print(f"Base reiniciada: {ruta}")

    from api.servidor import crear_servidor
    from aplicacion.casos_uso.contexto import Contexto
    from infraestructura.persistencia.semilla import esta_vacia, sembrar

    ctx = Contexto.abrir(str(ruta))
    if args.sembrar or esta_vacia(ctx):
        if esta_vacia(ctx):
            print("Base vacia: cargando los datos de ejemplo de la Parte IV.")
            r = sembrar(ctx)
            print(f"  {r['instrumentos']} instrumentos, {r['posiciones']} posiciones, "
                  f"{r['carga'].get('resumen', {}).get('nuevas', 0)} precios.")
            print("  Ve a Reproceso para valorizar el rango propuesto.")
        else:
            print("La base ya tiene instrumentos: no se siembra de nuevo.")

    servidor, _api = crear_servidor(str(ruta), args.puerto, args.host)
    url = f"http://{args.host}:{args.puerto}/"
    print("\n  Sistema de Valorizacion Interno - GOI")
    print(f"  Base de datos : {ruta}")
    print(f"  Aplicacion    : {url}")
    print("  Ctrl+C para detener.\n")
    if not args.sin_navegador:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")
    finally:
        servidor.server_close()
        # Vuelca el WAL al archivo principal para que la base quede completa en
        # un solo fichero y se pueda copiar o abrir con cualquier visor.
        try:
            ctx.bd.ejecutar("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
