"""Repositorios SQLite. Implementan los puertos de la capa de aplicacion.

Cero reglas de negocio aqui: solo lectura y escritura, y la conversion entre
el texto decimal exacto del almacenamiento y los Decimal del dominio.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Optional, Sequence

from dominio.configuracion import DEFECTOS, Parametros
from dominio.dinero import a_texto, dec
from dominio.fechas import a_iso, de_iso
from dominio.modelos import Instrumento, Posicion, Precio
from infraestructura.persistencia.db import BaseDatos

PORTAFOLIO = 1


def ahora() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _d(v: Any) -> Optional[Decimal]:
    return None if v is None or v == "" else dec(v)


class RepoInstrumentos:
    def __init__(self, bd: BaseDatos) -> None:
        self.bd = bd

    @staticmethod
    def _map(r) -> Instrumento:
        return Instrumento(
            isin=r["isin"],
            moneda=r["moneda"],
            tasa_cupon=dec(r["tasa_cupon"]),
            frecuencia=int(r["frecuencia"]),
            fecha_emision=de_iso(r["fecha_emision"]),
            fecha_vencimiento=de_iso(r["fecha_vencimiento"]),
            convencion=r["convencion"],
            precio_expresado_en=r["precio_expresado_en"],
            valor_redencion=dec(r["valor_redencion"]),
            descripcion=r["descripcion"] or "",
            eliminado_en=r["eliminado_en"],
        )

    def listar(self, incluir_eliminados: bool = False) -> list[Instrumento]:
        sql = "SELECT * FROM instrumento"
        if not incluir_eliminados:
            sql += " WHERE eliminado_en IS NULL"
        sql += " ORDER BY isin"
        return [self._map(r) for r in self.bd.consultar(sql)]

    def obtener(self, isin: str) -> Optional[Instrumento]:
        r = self.bd.uno("SELECT * FROM instrumento WHERE isin = ?", (isin,))
        return self._map(r) if r else None

    def guardar(self, i: Instrumento, usuario: str) -> None:
        self.bd.ejecutar(
            """INSERT INTO instrumento
               (isin, descripcion, moneda, tasa_cupon, frecuencia, fecha_emision,
                fecha_vencimiento, convencion, precio_expresado_en, valor_redencion,
                creado_en, creado_por)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(isin) DO UPDATE SET
                 descripcion=excluded.descripcion, moneda=excluded.moneda,
                 tasa_cupon=excluded.tasa_cupon, frecuencia=excluded.frecuencia,
                 fecha_emision=excluded.fecha_emision,
                 fecha_vencimiento=excluded.fecha_vencimiento,
                 convencion=excluded.convencion,
                 precio_expresado_en=excluded.precio_expresado_en,
                 valor_redencion=excluded.valor_redencion""",
            (i.isin, i.descripcion, i.moneda, a_texto(i.tasa_cupon), i.frecuencia,
             a_iso(i.fecha_emision), a_iso(i.fecha_vencimiento), i.convencion,
             i.precio_expresado_en, a_texto(i.valor_redencion), ahora(), usuario),
        )

    def eliminar(self, isin: str, usuario: str, motivo: str) -> None:
        self.bd.ejecutar(
            "UPDATE instrumento SET eliminado_en=?, eliminado_por=?, "
            "motivo_eliminacion=? WHERE isin=?",
            (ahora(), usuario, motivo, isin),
        )

    def reactivar(self, isin: str, usuario: str) -> None:
        self.bd.ejecutar(
            "UPDATE instrumento SET eliminado_en=NULL, eliminado_por=NULL, "
            "motivo_eliminacion=NULL WHERE isin=?",
            (isin,),
        )

    def guardar_calendario(self, isin: str, fechas: Sequence[date]) -> None:
        self.bd.ejecutar("DELETE FROM calendario_cupon WHERE isin=?", (isin,))
        self.bd.ejecutar_muchos(
            "INSERT INTO calendario_cupon (isin, fecha) VALUES (?,?)",
            [(isin, a_iso(f)) for f in fechas],
        )


class RepoPosiciones:
    def __init__(self, bd: BaseDatos) -> None:
        self.bd = bd

    @staticmethod
    def _map(r) -> Posicion:
        return Posicion(
            id=int(r["id"]),
            isin=r["isin"],
            nominal=dec(r["nominal"]),
            fecha_alta=de_iso(r["fecha_alta"]),
            eliminado_en=r["eliminado_en"],
        )

    def listar(self, incluir_eliminadas: bool = False) -> list[Posicion]:
        sql = "SELECT * FROM posicion"
        if not incluir_eliminadas:
            sql += " WHERE eliminado_en IS NULL"
        sql += " ORDER BY isin, fecha_alta, id"
        return [self._map(r) for r in self.bd.consultar(sql)]

    def obtener(self, id_posicion: int) -> Optional[Posicion]:
        r = self.bd.uno("SELECT * FROM posicion WHERE id=?", (id_posicion,))
        return self._map(r) if r else None

    def fila(self, id_posicion: int):
        return self.bd.uno("SELECT * FROM posicion WHERE id=?", (id_posicion,))

    def por_instrumento(self, isin: str, incluir_eliminadas: bool = False) -> list[Posicion]:
        sql = "SELECT * FROM posicion WHERE isin=?"
        if not incluir_eliminadas:
            sql += " AND eliminado_en IS NULL"
        return [self._map(r) for r in self.bd.consultar(sql, (isin,))]

    def guardar(self, p: Posicion, usuario: str) -> int:
        if p.id:
            self.bd.ejecutar(
                "UPDATE posicion SET isin=?, nominal=?, fecha_alta=? WHERE id=?",
                (p.isin, a_texto(p.nominal), a_iso(p.fecha_alta), p.id),
            )
            return p.id
        cur = self.bd.ejecutar(
            "INSERT INTO posicion (portafolio_id, isin, nominal, fecha_alta, creado_en, creado_por)"
            " VALUES (?,?,?,?,?,?)",
            (PORTAFOLIO, p.isin, a_texto(p.nominal), a_iso(p.fecha_alta), ahora(), usuario),
        )
        return int(cur.lastrowid)

    def eliminar(self, id_posicion: int, usuario: str, motivo: str) -> None:
        self.bd.ejecutar(
            "UPDATE posicion SET eliminado_en=?, eliminado_por=?, motivo_eliminacion=? WHERE id=?",
            (ahora(), usuario, motivo, id_posicion),
        )

    def reactivar(self, id_posicion: int, usuario: str) -> None:
        self.bd.ejecutar(
            "UPDATE posicion SET eliminado_en=NULL, eliminado_por=NULL, "
            "motivo_eliminacion=NULL WHERE id=?",
            (id_posicion,),
        )


class RepoPrecios:
    def __init__(self, bd: BaseDatos) -> None:
        self.bd = bd

    @staticmethod
    def _map(r) -> Precio:
        return Precio(
            fecha=de_iso(r["fecha"]),
            isin=r["isin"],
            precio=_d(r["precio"]),
            tipo_cambio=_d(r["tipo_cambio"]),
            fuente=r["fuente"] or "",
        )

    def por_instrumento(self, isin: str) -> list[Precio]:
        return [
            self._map(r)
            for r in self.bd.consultar(
                "SELECT * FROM precio WHERE isin=? AND eliminado_en IS NULL ORDER BY fecha",
                (isin,),
            )
        ]

    def todos(self) -> dict[str, list[Precio]]:
        salida: dict[str, list[Precio]] = {}
        for r in self.bd.consultar(
            "SELECT * FROM precio WHERE eliminado_en IS NULL ORDER BY isin, fecha"
        ):
            salida.setdefault(r["isin"], []).append(self._map(r))
        return salida

    def filas(self, isin: str | None = None, desde: date | None = None,
              hasta: date | None = None, incluir_eliminados: bool = False) -> list[dict]:
        sql = "SELECT * FROM precio WHERE 1=1"
        params: list[Any] = []
        if not incluir_eliminados:
            sql += " AND eliminado_en IS NULL"
        if isin:
            sql += " AND isin=?"
            params.append(isin)
        if desde:
            sql += " AND fecha>=?"
            params.append(a_iso(desde))
        if hasta:
            sql += " AND fecha<=?"
            params.append(a_iso(hasta))
        sql += " ORDER BY fecha DESC, isin LIMIT 5000"
        return [dict(r) for r in self.bd.consultar(sql, params)]

    def upsert(self, fecha: date, isin: str, precio: Optional[Decimal],
               tipo_cambio: Optional[Decimal], fuente: str, carga_id: Optional[int],
               usuario: str) -> None:
        existente = self.bd.uno(
            "SELECT id FROM precio WHERE fecha=? AND isin=? AND eliminado_en IS NULL",
            (a_iso(fecha), isin),
        )
        if existente:
            self.bd.ejecutar(
                "UPDATE precio SET precio=?, tipo_cambio=?, fuente=?, carga_id=?, "
                "cargado_en=?, cargado_por=? WHERE id=?",
                (a_texto(precio), a_texto(tipo_cambio), fuente, carga_id, ahora(),
                 usuario, existente["id"]),
            )
        else:
            self.bd.ejecutar(
                "INSERT INTO precio (fecha, isin, precio, tipo_cambio, fuente, carga_id,"
                " cargado_en, cargado_por) VALUES (?,?,?,?,?,?,?,?)",
                (a_iso(fecha), isin, a_texto(precio), a_texto(tipo_cambio), fuente,
                 carga_id, ahora(), usuario),
            )

    def eliminar(self, id_precio: int, usuario: str, motivo: str) -> Optional[dict]:
        r = self.bd.uno("SELECT * FROM precio WHERE id=?", (id_precio,))
        if not r:
            return None
        self.bd.ejecutar(
            "UPDATE precio SET eliminado_en=?, eliminado_por=?, motivo_eliminacion=? WHERE id=?",
            (ahora(), usuario, motivo, id_precio),
        )
        return dict(r)

    def huerfanos(self) -> list[dict]:
        return [
            dict(r)
            for r in self.bd.consultar(
                "SELECT p.isin, COUNT(*) AS n, MIN(p.fecha) AS desde, MAX(p.fecha) AS hasta "
                "FROM precio p LEFT JOIN instrumento i ON i.isin = p.isin "
                "WHERE p.eliminado_en IS NULL AND (i.isin IS NULL OR i.eliminado_en IS NOT NULL) "
                "GROUP BY p.isin ORDER BY p.isin"
            )
        ]

    def purgar_huerfanos(self, isin: str, usuario: str, motivo: str) -> int:
        cur = self.bd.ejecutar(
            "UPDATE precio SET eliminado_en=?, eliminado_por=?, motivo_eliminacion=? "
            "WHERE isin=? AND eliminado_en IS NULL",
            (ahora(), usuario, motivo, isin),
        )
        return cur.rowcount


class RepoParametros:
    def __init__(self, bd: BaseDatos) -> None:
        self.bd = bd

    def mapa(self) -> dict[str, str]:
        base = dict(DEFECTOS)
        for r in self.bd.consultar(
            "SELECT clave, valor FROM parametro WHERE portafolio_id=?", (PORTAFOLIO,)
        ):
            base[r["clave"]] = r["valor"]
        return base

    def leer(self) -> Parametros:
        return Parametros.desde_mapa(self.mapa())

    def escribir(self, cambios: dict[str, str], usuario: str) -> None:
        for k, v in cambios.items():
            if k not in DEFECTOS:
                raise ValueError(f"Parametro desconocido: {k}")
            self.bd.ejecutar(
                "INSERT INTO parametro (portafolio_id, clave, valor) VALUES (?,?,?) "
                "ON CONFLICT(portafolio_id, clave) DO UPDATE SET valor=excluded.valor",
                (PORTAFOLIO, k, str(v)),
            )


class RepoBitacora:
    def __init__(self, bd: BaseDatos) -> None:
        self.bd = bd

    def registrar(self, accion: str, usuario: str, entidad: str = "", entidad_id: str = "",
                  detalle: Any = None, rango_desde: Optional[date] = None,
                  rango_hasta: Optional[date] = None,
                  valorizaciones_cambiadas: Optional[int] = None) -> None:
        self.bd.ejecutar(
            "INSERT INTO bitacora (momento, usuario, accion, entidad, entidad_id, detalle,"
            " rango_desde, rango_hasta, valorizaciones_cambiadas) VALUES (?,?,?,?,?,?,?,?,?)",
            (ahora(), usuario, accion, entidad, str(entidad_id),
             json.dumps(detalle, ensure_ascii=False, default=str) if detalle is not None else None,
             a_iso(rango_desde), a_iso(rango_hasta), valorizaciones_cambiadas),
        )

    def listar(self, limite: int = 300) -> list[dict]:
        return [dict(r) for r in self.bd.consultar(
            "SELECT * FROM bitacora ORDER BY id DESC LIMIT ?", (limite,))]


class RepoDesactualizadas:
    def __init__(self, bd: BaseDatos) -> None:
        self.bd = bd

    def marcar(self, fechas: Iterable[date], isin: str, motivo: str) -> int:
        filas = [(PORTAFOLIO, a_iso(f), isin, motivo, ahora()) for f in fechas]
        self.bd.ejecutar_muchos(
            "INSERT INTO fecha_desactualizada (portafolio_id, fecha, isin, motivo, marcado_en)"
            " VALUES (?,?,?,?,?) ON CONFLICT(portafolio_id, fecha, isin) DO UPDATE SET"
            " motivo=excluded.motivo, marcado_en=excluded.marcado_en",
            filas,
        )
        return len(filas)

    def listar(self) -> list[dict]:
        return [dict(r) for r in self.bd.consultar(
            "SELECT * FROM fecha_desactualizada WHERE portafolio_id=? ORDER BY fecha, isin",
            (PORTAFOLIO,))]

    def resumen(self) -> list[dict]:
        return [dict(r) for r in self.bd.consultar(
            "SELECT isin, MIN(fecha) AS desde, MAX(fecha) AS hasta, COUNT(*) AS n, motivo "
            "FROM fecha_desactualizada WHERE portafolio_id=? GROUP BY isin, motivo "
            "ORDER BY isin", (PORTAFOLIO,))]

    def limpiar_rango(self, desde: date, hasta: date, isines: Sequence[str] | None) -> None:
        sql = ("DELETE FROM fecha_desactualizada WHERE portafolio_id=? "
               "AND fecha>=? AND fecha<=?")
        params: list[Any] = [PORTAFOLIO, a_iso(desde), a_iso(hasta)]
        if isines:
            sql += " AND isin IN (%s)" % ",".join("?" * len(isines))
            params.extend(isines)
        self.bd.ejecutar(sql, params)


class RepoPeriodos:
    def __init__(self, bd: BaseDatos) -> None:
        self.bd = bd

    def cerrados(self) -> list[dict]:
        return [dict(r) for r in self.bd.consultar(
            "SELECT * FROM periodo_cerrado WHERE portafolio_id=? AND reabierto_en IS NULL "
            "ORDER BY fecha_desde", (PORTAFOLIO,))]

    def interseccion(self, desde: date, hasta: date) -> list[dict]:
        return [p for p in self.cerrados()
                if not (a_iso(hasta) < p["fecha_desde"] or a_iso(desde) > p["fecha_hasta"])]

    def cerrar(self, desde: date, hasta: date, usuario: str) -> int:
        cur = self.bd.ejecutar(
            "INSERT INTO periodo_cerrado (portafolio_id, fecha_desde, fecha_hasta,"
            " cerrado_en, cerrado_por) VALUES (?,?,?,?,?)",
            (PORTAFOLIO, a_iso(desde), a_iso(hasta), ahora(), usuario),
        )
        return int(cur.lastrowid)

    def reabrir(self, id_periodo: int, usuario: str, justificacion: str) -> None:
        if not justificacion or not justificacion.strip():
            raise ValueError("La reapertura de un periodo cerrado exige justificacion.")
        self.bd.ejecutar(
            "UPDATE periodo_cerrado SET reabierto_en=?, reabierto_por=?, justificacion=? WHERE id=?",
            (ahora(), usuario, justificacion, id_periodo),
        )
