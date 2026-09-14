"""Persistencia bitemporal de la valorizacion. Recalcular versiona, no sobreescribe."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Optional, Sequence

from dominio.dinero import a_texto, dec
from dominio.fechas import a_iso
from dominio.valorizacion.corrida import Fila
from infraestructura.persistencia.db import BaseDatos
from infraestructura.persistencia.repositorios import PORTAFOLIO, ahora

CAMPOS = [
    "fecha_valorizacion", "isin", "version_calculo", "posicion_id", "nominal", "vigente",
    "fecha_devengo", "ultimo_cupon", "proximo_cupon", "dias_transcurridos", "dias_periodo",
    "cupon_por_periodo", "devengo_por_100", "precio_proveedor", "precio_local", "tipo_cambio",
    "precio_imputado", "tipo_cambio_imputado", "dias_arrastre_precio", "fecha_origen_precio",
    "fecha_origen_tipo_cambio", "security_mv_local", "devengo_local", "total_mv_local", "fx",
    "security_mv_base", "devengo_base", "total_mv_base", "caja_origen", "caja_base",
    "begin_mv", "efecto_precio_fx", "devengo_dia", "cupon_pagado", "alta_posicion",
    "baja_vencimiento", "cobros_dia", "efecto_fx_caja", "end_mv", "control",
    "devengo_por_100_t0", "dias_transcurridos_t0", "dias_periodo_t0", "ultimo_cupon_t0",
    "proximo_cupon_t0", "security_mv_base_t0", "devengo_base_t0", "total_mv_base_t0",
    "quiebre_t0", "devengo_diario", "evento", "error",
]

# Campos que definen si dos calculos son el mismo resultado. La comparacion de
# idempotencia se hace sobre esto, no sobre el instante de calculo.
CAMPOS_COMPARABLES = [c for c in CAMPOS if c != "version_calculo"]


def fila_a_registro(f: Fila) -> dict[str, Any]:
    v = f.valorizacion
    t0 = f.control_t0
    p = f.puente
    return {
        "fecha_valorizacion": a_iso(v.fecha_valorizacion),
        "isin": v.isin,
        "version_calculo": None,
        "posicion_id": v.posicion_id,
        "nominal": a_texto(v.nominal),
        "vigente": 1 if v.vigente else 0,
        "fecha_devengo": a_iso(v.fecha_devengo),
        "ultimo_cupon": a_iso(v.ultimo_cupon),
        "proximo_cupon": a_iso(v.proximo_cupon),
        "dias_transcurridos": v.dias_transcurridos,
        "dias_periodo": v.dias_periodo,
        "cupon_por_periodo": a_texto(v.cupon_por_periodo),
        "devengo_por_100": a_texto(v.devengo_por_100),
        "precio_proveedor": a_texto(v.precio_proveedor),
        "precio_local": a_texto(v.precio_local),
        "tipo_cambio": a_texto(v.tipo_cambio),
        "precio_imputado": 1 if v.precio_imputado else 0,
        "tipo_cambio_imputado": 1 if v.tipo_cambio_imputado else 0,
        "dias_arrastre_precio": v.dias_arrastre_precio,
        "fecha_origen_precio": a_iso(v.fecha_origen_precio),
        "fecha_origen_tipo_cambio": a_iso(v.fecha_origen_tipo_cambio),
        "security_mv_local": a_texto(v.security_mv_local),
        "devengo_local": a_texto(v.devengo_local),
        "total_mv_local": a_texto(v.total_mv_local),
        "fx": a_texto(v.fx),
        "security_mv_base": a_texto(v.security_mv_base),
        "devengo_base": a_texto(v.devengo_base),
        "total_mv_base": a_texto(v.total_mv_base),
        "caja_origen": a_texto(f.caja_origen),
        "caja_base": a_texto(f.caja_base),
        "begin_mv": a_texto(p.begin_mv),
        "efecto_precio_fx": a_texto(p.efecto_precio_fx),
        "devengo_dia": a_texto(p.devengo_dia),
        "cupon_pagado": a_texto(p.cupon_pagado),
        "alta_posicion": a_texto(p.alta_posicion),
        "baja_vencimiento": a_texto(p.baja_vencimiento),
        "cobros_dia": a_texto(p.cobros_dia),
        "efecto_fx_caja": a_texto(p.efecto_fx_caja),
        "end_mv": a_texto(p.end_mv),
        "control": a_texto(p.control),
        "devengo_por_100_t0": a_texto(t0.devengo_por_100) if t0 else None,
        "dias_transcurridos_t0": t0.dias_transcurridos if t0 else None,
        "dias_periodo_t0": t0.dias_periodo if t0 else None,
        "ultimo_cupon_t0": a_iso(t0.ultimo_cupon) if t0 else None,
        "proximo_cupon_t0": a_iso(t0.proximo_cupon) if t0 else None,
        "security_mv_base_t0": a_texto(t0.security_mv_base) if t0 else None,
        "devengo_base_t0": a_texto(t0.devengo_base) if t0 else None,
        "total_mv_base_t0": a_texto(t0.total_mv_base) if t0 else None,
        "quiebre_t0": a_texto(f.quiebre_t0),
        "devengo_diario": a_texto(f.devengo_diario),
        "evento": v.evento,
        "error": v.error,
    }


class RepoValorizacion:
    def __init__(self, bd: BaseDatos) -> None:
        self.bd = bd

    # --- versiones --------------------------------------------------------
    def crear_version(self, reproceso_id: int, usuario: str, desde: date, hasta: date) -> int:
        cur = self.bd.ejecutar(
            "INSERT INTO version_calculo (portafolio_id, reproceso_id, calculado_en,"
            " calculado_por, fecha_desde, fecha_hasta, publicada) VALUES (?,?,?,?,?,?,1)",
            (PORTAFOLIO, reproceso_id, ahora(), usuario, a_iso(desde), a_iso(hasta)),
        )
        return int(cur.lastrowid)

    def versiones_de_fecha(self, fecha: date) -> list[dict]:
        return [dict(r) for r in self.bd.consultar(
            "SELECT vc.*, COUNT(v.isin) AS filas FROM version_calculo vc "
            "JOIN valorizacion v ON v.version_calculo = vc.id "
            "WHERE v.fecha_valorizacion = ? GROUP BY vc.id ORDER BY vc.id DESC",
            (a_iso(fecha),))]

    def versiones(self) -> list[dict]:
        return [dict(r) for r in self.bd.consultar(
            "SELECT vc.*, COUNT(v.isin) AS filas FROM version_calculo vc "
            "LEFT JOIN valorizacion v ON v.version_calculo = vc.id "
            "GROUP BY vc.id ORDER BY vc.id DESC LIMIT 200")]

    # --- escritura --------------------------------------------------------
    def publicar(self, version_id: int, registros: Sequence[dict]) -> None:
        cols = ",".join(CAMPOS)
        marcas = ",".join("?" * len(CAMPOS))
        filas = []
        for r in registros:
            r = dict(r)
            r["version_calculo"] = version_id
            filas.append([r.get(c) for c in CAMPOS])
        self.bd.ejecutar_muchos(
            f"INSERT INTO valorizacion ({cols}) VALUES ({marcas})", filas
        )

    # --- lectura ----------------------------------------------------------
    def vigentes(self, desde: date, hasta: date, isines: Sequence[str] | None = None,
                 version: Optional[int] = None) -> list[dict]:
        tabla = "valorizacion" if version else "valorizacion_vigente"
        sql = f"SELECT * FROM {tabla} WHERE fecha_valorizacion>=? AND fecha_valorizacion<=?"
        params: list[Any] = [a_iso(desde), a_iso(hasta)]
        if version:
            sql += " AND version_calculo=?"
            params.append(version)
        if isines:
            sql += " AND isin IN (%s)" % ",".join("?" * len(isines))
            params.extend(isines)
        sql += " ORDER BY fecha_valorizacion, isin"
        return [dict(r) for r in self.bd.consultar(sql, params)]

    def mapa_vigente(self, desde: date, hasta: date) -> dict[tuple[str, str], dict]:
        return {
            (r["fecha_valorizacion"], r["isin"]): r
            for r in self.vigentes(desde, hasta)
        }

    def rango_disponible(self) -> tuple[Optional[str], Optional[str]]:
        r = self.bd.uno(
            "SELECT MIN(fecha_valorizacion) a, MAX(fecha_valorizacion) b FROM valorizacion"
        )
        return (r["a"], r["b"]) if r else (None, None)

    def fechas_con_valorizacion(self, isin: str) -> list[str]:
        return [r["fecha_valorizacion"] for r in self.bd.consultar(
            "SELECT DISTINCT fecha_valorizacion FROM valorizacion_vigente WHERE isin=? "
            "ORDER BY fecha_valorizacion", (isin,))]

    def total_portafolio(self, fecha: date, incluir_caja: bool) -> Decimal:
        filas = self.vigentes(fecha, fecha)
        total = dec(0)
        for r in filas:
            total += dec(r["total_mv_base"] or 0)
            if incluir_caja:
                total += dec(r["caja_base"] or 0)
        return total
