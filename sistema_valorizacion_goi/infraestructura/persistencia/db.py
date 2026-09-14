"""Conexion SQLite y migraciones versionadas. Sin cambios de esquema manuales."""
from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable, Optional

RAIZ = Path(__file__).resolve().parents[2]
DIR_MIGRACIONES = RAIZ / "migraciones"

_local = threading.local()


def sentencias(script: str) -> list[str]:
    """Divide un script SQL en sentencias, descartando comentarios de linea.

    Se ejecutan una a una dentro de una transaccion: executescript haria COMMIT
    implicito y la migracion dejaria de ser atomica.
    """
    sin_comentarios = "\n".join(
        re.sub(r"--.*$", "", linea) for linea in script.splitlines()
    )
    return [s.strip() for s in sin_comentarios.split(";") if s.strip()]


class BaseDatos:
    def __init__(self, ruta: str | Path) -> None:
        self.ruta = str(ruta)

    def conexion(self) -> sqlite3.Connection:
        cn = getattr(_local, "cn_" + str(abs(hash(self.ruta))), None)
        if cn is None:
            cn = sqlite3.connect(self.ruta, timeout=30, isolation_level=None)
            cn.row_factory = sqlite3.Row
            cn.execute("PRAGMA journal_mode=WAL")
            cn.execute("PRAGMA foreign_keys=ON")
            cn.execute("PRAGMA synchronous=NORMAL")
            setattr(_local, "cn_" + str(abs(hash(self.ruta))), cn)
        return cn

    # --- utilidades -------------------------------------------------------
    def consultar(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return list(self.conexion().execute(sql, tuple(params)))

    def uno(self, sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
        filas = self.consultar(sql, params)
        return filas[0] if filas else None

    def ejecutar(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self.conexion().execute(sql, tuple(params))

    def ejecutar_muchos(self, sql: str, filas: Iterable[Iterable[Any]]) -> None:
        self.conexion().executemany(sql, [tuple(f) for f in filas])

    def transaccion(self) -> "Transaccion":
        return Transaccion(self.conexion())

    # --- migraciones ------------------------------------------------------
    def migrar(self) -> list[str]:
        cn = self.conexion()
        cn.execute(
            "CREATE TABLE IF NOT EXISTS migracion ("
            " version TEXT PRIMARY KEY, aplicada_en TEXT NOT NULL)"
        )
        aplicadas = {r["version"] for r in cn.execute("SELECT version FROM migracion")}
        nuevas: list[str] = []
        archivos = sorted(
            p for p in DIR_MIGRACIONES.glob("*.sql") if not p.name.endswith(".abajo.sql")
        )
        for archivo in archivos:
            version = archivo.stem
            if version in aplicadas:
                continue
            cn.execute("BEGIN")
            try:
                for sentencia in sentencias(archivo.read_text(encoding="utf-8")):
                    cn.execute(sentencia)
                cn.execute(
                    "INSERT INTO migracion (version, aplicada_en) "
                    "VALUES (?, datetime('now'))",
                    (version,),
                )
                cn.execute("COMMIT")
            except Exception:
                cn.execute("ROLLBACK")
                raise
            nuevas.append(version)
        return nuevas

    def revertir(self, version: str) -> None:
        archivo = DIR_MIGRACIONES / f"{version}.abajo.sql"
        if not archivo.exists():
            raise FileNotFoundError(f"No existe la migracion reversible {version}.")
        cn = self.conexion()
        cn.execute("BEGIN")
        try:
            for sentencia in sentencias(archivo.read_text(encoding="utf-8")):
                cn.execute(sentencia)
            cn.execute("DELETE FROM migracion WHERE version = ?", (version,))
            cn.execute("COMMIT")
        except Exception:
            cn.execute("ROLLBACK")
            raise


class Transaccion:
    def __init__(self, cn: sqlite3.Connection) -> None:
        self.cn = cn

    def __enter__(self) -> sqlite3.Connection:
        self.cn.execute("BEGIN IMMEDIATE")
        return self.cn

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.cn.execute("COMMIT")
        else:
            self.cn.execute("ROLLBACK")
        return False
