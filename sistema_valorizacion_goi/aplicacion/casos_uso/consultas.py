"""Consultas de presentacion: grillas, consolidados, comparador de versiones."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, Sequence

from aplicacion.casos_uso.contexto import Contexto
from dominio.control.control_t0 import clasificar_quiebre
from dominio.dinero import CERO, a_texto, dec
from dominio.fechas import a_iso, de_iso
from infraestructura.persistencia.repo_valorizacion import CAMPOS_COMPARABLES

COLUMNAS_VALORIZACION = [
    "fecha_valorizacion", "isin", "nominal", "vigente", "fecha_devengo", "ultimo_cupon",
    "proximo_cupon", "dias_transcurridos", "dias_periodo", "cupon_por_periodo",
    "devengo_por_100", "precio_proveedor", "precio_local", "tipo_cambio",
    "precio_imputado", "tipo_cambio_imputado", "dias_arrastre_precio",
    "fecha_origen_precio", "fecha_origen_tipo_cambio", "security_mv_local",
    "devengo_local", "total_mv_local", "fx", "security_mv_base", "devengo_base",
    "total_mv_base", "devengo_por_100_t0", "total_mv_base_t0", "quiebre_t0",
    "evento", "error", "version_calculo",
]

COLUMNAS_PUENTE = [
    "fecha_valorizacion", "isin", "begin_mv", "efecto_precio_fx", "devengo_dia",
    "cupon_pagado", "alta_posicion", "baja_vencimiento", "cobros_dia",
    "efecto_fx_caja", "end_mv", "control", "caja_origen", "caja_base", "evento",
]


def grilla(ctx: Contexto, desde: date, hasta: date, isines: Sequence[str] | None = None,
           version: Optional[int] = None) -> dict:
    filas = ctx.valorizacion.vigentes(desde, hasta, isines, version)
    p = ctx.parametros.leer()
    return {
        "desde": a_iso(desde), "hasta": a_iso(hasta),
        "columnas": COLUMNAS_VALORIZACION,
        "filas": filas,
        "consolidado": consolidado(ctx, desde, hasta, isines, version)["filas"],
        "parametros": p.a_mapa(),
    }


def consolidado(ctx: Contexto, desde: date, hasta: date,
                isines: Sequence[str] | None = None,
                version: Optional[int] = None) -> dict:
    p = ctx.parametros.leer()
    filas = ctx.valorizacion.vigentes(desde, hasta, isines, version)
    por_fecha: dict[str, dict] = {}
    for f in filas:
        d = por_fecha.setdefault(f["fecha_valorizacion"], {
            "fecha": f["fecha_valorizacion"], "posiciones": 0,
            **{k: CERO for k in ("total_mv_base", "total_mv_base_t0", "caja_base",
                                 "begin_mv", "end_mv", "efecto_precio_fx", "devengo_dia",
                                 "cupon_pagado", "alta_posicion", "baja_vencimiento",
                                 "cobros_dia", "efecto_fx_caja", "control", "quiebre_t0",
                                 "devengo_diario", "security_mv_base", "devengo_base")},
            "eventos": [],
        })
        d["posiciones"] += 1 if f["vigente"] else 0
        for k in ("total_mv_base", "total_mv_base_t0", "begin_mv", "end_mv",
                  "efecto_precio_fx", "devengo_dia", "cupon_pagado", "alta_posicion",
                  "baja_vencimiento", "cobros_dia", "efecto_fx_caja", "control",
                  "quiebre_t0", "devengo_diario", "security_mv_base", "devengo_base"):
            d[k] += dec(f.get(k) or 0)
        # El saldo de caja se calcula siempre, pero solo entra al consolidado
        # cuando el parametro lo activa: mostrarlo fuera del Total MV invita a
        # leer un efectivo que no esta en la cifra del portafolio.
        if p.incluir_caja:
            d["caja_base"] += dec(f.get("caja_base") or 0)
        if f.get("evento"):
            d["eventos"].append(f"{f['evento']} {f['isin']}")

    salida = []
    for fecha in sorted(por_fecha):
        d = por_fecha[fecha]
        estado, residual = clasificar_quiebre(d["quiebre_t0"], d["devengo_diario"],
                                              p.tolerancia_quiebre)
        fila = {k: (a_texto(v) if isinstance(v, Decimal) else v) for k, v in d.items()}
        fila["estado_quiebre"] = estado
        fila["residual"] = a_texto(residual)
        fila["eventos"] = ", ".join(d["eventos"])
        salida.append(fila)
    return {"filas": salida, "incluir_caja": p.incluir_caja}


def puente(ctx: Contexto, desde: date, hasta: date, isines: Sequence[str] | None = None,
           version: Optional[int] = None) -> dict:
    filas = ctx.valorizacion.vigentes(desde, hasta, isines, version)
    p = ctx.parametros.leer()
    # La division decimal de un cociente no exacto -por ejemplo 1/1.3804- deja
    # un residuo en el digito 20. El control se contrasta contra la tolerancia
    # declarada, nunca por igualdad exacta.
    return {
        "columnas": COLUMNAS_PUENTE,
        "filas": filas,
        "consolidado": consolidado(ctx, desde, hasta, isines, version)["filas"],
        "incluir_caja": p.incluir_caja,
        "tolerancia": a_texto(p.tolerancia_quiebre),
        "filas_con_control_no_cero": [
            {"fecha": f["fecha_valorizacion"], "isin": f["isin"], "control": f["control"]}
            for f in filas
            if f["control"] and abs(dec(f["control"])) > p.tolerancia_quiebre
        ],
    }


def comparar_versiones(ctx: Contexto, fecha: date, version_a: int,
                       version_b: int) -> dict:
    a = {r["isin"]: r for r in ctx.valorizacion.vigentes(fecha, fecha, None, version_a)}
    b = {r["isin"]: r for r in ctx.valorizacion.vigentes(fecha, fecha, None, version_b)}
    isines = sorted(set(a) | set(b))
    filas = []
    for isin in isines:
        ra, rb = a.get(isin), b.get(isin)
        campos = []
        if ra and rb:
            campos = [c for c in CAMPOS_COMPARABLES
                      if str(ra.get(c)) != str(rb.get(c))]
        va = dec(ra["total_mv_base"] or 0) if ra else CERO
        vb = dec(rb["total_mv_base"] or 0) if rb else CERO
        filas.append({
            "isin": isin,
            "presente_en_a": ra is not None, "presente_en_b": rb is not None,
            "total_a": a_texto(va), "total_b": a_texto(vb),
            "diferencia": a_texto(vb - va),
            "diferencia_relativa": a_texto((vb - va) / va) if va != 0 else None,
            "campos_distintos": campos,
            "fila_a": ra, "fila_b": rb,
        })
    return {
        "fecha": a_iso(fecha), "version_a": version_a, "version_b": version_b,
        "filas": filas,
        "total_a": a_texto(sum((dec(r["total_mv_base"] or 0) for r in a.values()), CERO)),
        "total_b": a_texto(sum((dec(r["total_mv_base"] or 0) for r in b.values()), CERO)),
    }


def trazabilidad(ctx: Contexto, fecha: date, isin: str) -> dict:
    """Desde cualquier Total MV al detalle, y del detalle al precio que lo origino."""
    filas = ctx.valorizacion.vigentes(fecha, fecha, [isin])
    fila = filas[0] if filas else None
    origen = fila.get("fecha_origen_precio") if fila else None
    precio = ctx.bd.uno(
        "SELECT * FROM precio WHERE isin=? AND fecha=? AND eliminado_en IS NULL",
        (isin, origen or a_iso(fecha)),
    )
    instr = ctx.instrumentos.obtener(isin)
    return {
        "valorizacion": fila,
        "precio_origen": dict(precio) if precio else None,
        "instrumento": {
            "isin": isin, "moneda": instr.moneda, "convencion": instr.convencion,
            "precio_expresado_en": instr.precio_expresado_en,
            "tasa_cupon": a_texto(instr.tasa_cupon), "frecuencia": instr.frecuencia,
            "fecha_emision": a_iso(instr.fecha_emision),
            "fecha_vencimiento": a_iso(instr.fecha_vencimiento),
        } if instr else None,
        "calendario": [r["fecha"] for r in ctx.bd.consultar(
            "SELECT fecha FROM calendario_cupon WHERE isin=? ORDER BY fecha", (isin,))],
        "versiones": ctx.valorizacion.versiones_de_fecha(fecha),
    }
