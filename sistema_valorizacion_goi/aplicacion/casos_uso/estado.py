"""Estado del instrumento y bandeja de pendientes. Seccion 5."""
from __future__ import annotations

from datetime import date
from typing import Optional, Sequence

from dominio.fechas import a_iso, de_iso, rango_fechas
from dominio.modelos import (
    ESTADO_COBERTURA_PARCIAL,
    ESTADO_LISTO,
    ESTADO_REGISTRADO,
    ESTADO_SIN_PRECIOS,
    ESTADO_VALORIZADO,
    Instrumento,
    Posicion,
)
from aplicacion.casos_uso.contexto import Contexto

__all__ = ["rango_obligatorio", "estado_instrumentos", "bandeja_pendientes"]


def rango_obligatorio(
    instrumento: Instrumento, posicion: Posicion, hoy: date
) -> tuple[date, date]:
    """Desde fecha_alta hasta min(hoy, fecha_vencimiento)."""
    return posicion.fecha_alta, min(hoy, instrumento.fecha_vencimiento)


def estado_instrumentos(ctx: Contexto, hoy: Optional[date] = None) -> list[dict]:
    hoy = hoy or date.today()
    p = ctx.parametros.leer()
    instrumentos = {i.isin: i for i in ctx.instrumentos.listar()}
    posiciones = ctx.posiciones.listar()
    precios = ctx.precios.todos()
    desactualizadas = {}
    for d in ctx.desactualizadas.listar():
        desactualizadas.setdefault(d["isin"], []).append(d["fecha"])

    salida: list[dict] = []
    con_posicion = set()

    for pos in posiciones:
        instr = instrumentos.get(pos.isin)
        if instr is None:
            continue
        con_posicion.add(pos.isin)
        desde, hasta = rango_obligatorio(instr, pos, hoy)
        fechas_precio = {a_iso(x.fecha) for x in precios.get(pos.isin, [])
                         if x.precio is not None}
        requeridas = [f for f in rango_fechas(desde, hasta)]
        faltantes = [a_iso(f) for f in requeridas if a_iso(f) not in fechas_precio]
        valorizadas = set(ctx.valorizacion.fechas_con_valorizacion(pos.isin))
        pendientes_recalculo = desactualizadas.get(pos.isin, [])

        if not fechas_precio:
            estado = ESTADO_SIN_PRECIOS
        elif faltantes:
            estado = ESTADO_COBERTURA_PARCIAL
        elif pendientes_recalculo or not valorizadas.issuperset(
            {a_iso(f) for f in requeridas}
        ):
            estado = ESTADO_LISTO
        else:
            estado = ESTADO_VALORIZADO

        salida.append({
            "isin": pos.isin,
            "posicion_id": pos.id,
            "descripcion": instr.descripcion,
            "moneda": instr.moneda,
            "nominal": str(pos.nominal),
            "fecha_alta": a_iso(pos.fecha_alta),
            "fecha_vencimiento": a_iso(instr.fecha_vencimiento),
            "estado": estado,
            "rango_desde": a_iso(desde),
            "rango_hasta": a_iso(hasta),
            "dias_requeridos": len(requeridas),
            "dias_cubiertos": len(requeridas) - len(faltantes),
            "fechas_faltantes": faltantes[:400],
            "fechas_faltantes_total": len(faltantes),
            "fechas_desactualizadas": len(pendientes_recalculo),
            "desactualizadas_desde": min(pendientes_recalculo) if pendientes_recalculo else None,
            "desactualizadas_hasta": max(pendientes_recalculo) if pendientes_recalculo else None,
        })

    for isin, instr in instrumentos.items():
        if isin in con_posicion:
            continue
        salida.append({
            "isin": isin,
            "posicion_id": None,
            "descripcion": instr.descripcion,
            "moneda": instr.moneda,
            "nominal": None,
            "fecha_alta": None,
            "fecha_vencimiento": a_iso(instr.fecha_vencimiento),
            "estado": ESTADO_REGISTRADO,
            "rango_desde": None,
            "rango_hasta": None,
            "dias_requeridos": 0,
            "dias_cubiertos": 0,
            "fechas_faltantes": [],
            "fechas_faltantes_total": 0,
            "fechas_desactualizadas": 0,
            "desactualizadas_desde": None,
            "desactualizadas_hasta": None,
        })

    salida.sort(key=lambda x: (x["estado"] == ESTADO_VALORIZADO, x["isin"]))
    return salida


def bandeja_pendientes(ctx: Contexto, hoy: Optional[date] = None) -> dict:
    """Pantalla de inicio. Lista todo lo incompleto con su enlace de resolucion."""
    estados = estado_instrumentos(ctx, hoy)
    pendientes: list[dict] = []

    for e in estados:
        if e["estado"] == ESTADO_REGISTRADO:
            pendientes.append({
                "tipo": "SIN_POSICION",
                "isin": e["isin"],
                "titulo": f"{e['isin']} esta registrado en la maestra y no tiene posicion",
                "detalle": "Registra el nominal y la fecha de alta en cartera.",
                "modulo": "registro",
                "parametros": {"isin": e["isin"]},
            })
        elif e["estado"] == ESTADO_SIN_PRECIOS:
            pendientes.append({
                "tipo": "SIN_PRECIOS",
                "isin": e["isin"],
                "titulo": f"{e['isin']} no tiene ningun precio cargado",
                "detalle": (f"Faltan {e['fechas_faltantes_total']} fechas entre "
                            f"{e['rango_desde']} y {e['rango_hasta']}."),
                "modulo": "precios",
                "parametros": {"isin": e["isin"], "desde": e["rango_desde"],
                               "hasta": e["rango_hasta"]},
            })
        elif e["estado"] == ESTADO_COBERTURA_PARCIAL:
            pendientes.append({
                "tipo": "COBERTURA_PARCIAL",
                "isin": e["isin"],
                "titulo": f"{e['isin']} tiene cobertura parcial de precios",
                "detalle": (f"{e['dias_cubiertos']} de {e['dias_requeridos']} fechas cubiertas. "
                            f"Faltan {e['fechas_faltantes_total']}, desde "
                            f"{e['fechas_faltantes'][0] if e['fechas_faltantes'] else '-'}."),
                "modulo": "precios",
                "parametros": {"isin": e["isin"], "desde": e["rango_desde"],
                               "hasta": e["rango_hasta"]},
                "fechas_faltantes": e["fechas_faltantes"][:60],
            })
        elif e["estado"] == ESTADO_LISTO:
            pendientes.append({
                "tipo": "PENDIENTE_RECALCULO",
                "isin": e["isin"],
                "titulo": f"{e['isin']} esta listo y su valorizacion esta pendiente",
                "detalle": (f"{e['fechas_desactualizadas']} fechas desactualizadas"
                            + (f" entre {e['desactualizadas_desde']} y {e['desactualizadas_hasta']}."
                               if e["desactualizadas_desde"] else
                               f". Sin valorizar entre {e['rango_desde']} y {e['rango_hasta']}.")),
                "modulo": "reproceso",
                "parametros": {"isin": e["isin"],
                               "desde": e["desactualizadas_desde"] or e["rango_desde"],
                               "hasta": e["desactualizadas_hasta"] or e["rango_hasta"]},
            })

    # Eliminaciones pendientes de reprocesar.
    for r in ctx.bd.consultar(
        "SELECT p.id, p.isin, p.motivo_eliminacion FROM posicion p "
        "WHERE p.eliminado_en IS NOT NULL AND EXISTS ("
        "  SELECT 1 FROM valorizacion_vigente v WHERE v.isin = p.isin"
        "  AND v.posicion_id = p.id AND v.vigente = 1)"
    ):
        pendientes.append({
            "tipo": "ELIMINACION_PENDIENTE",
            "isin": r["isin"],
            "titulo": f"La posicion {r['id']} de {r['isin']} fue eliminada y sigue valorizada",
            "detalle": f"Motivo: {r['motivo_eliminacion'] or '-'}. Reprocesa el rango afectado.",
            "modulo": "reproceso",
            "parametros": {"isin": r["isin"]},
        })

    for h in ctx.precios.huerfanos():
        pendientes.append({
            "tipo": "PRECIOS_HUERFANOS",
            "isin": h["isin"],
            "titulo": f"Serie de precios huerfana de {h['isin']}",
            "detalle": (f"{h['n']} registros entre {h['desde']} y {h['hasta']} de un "
                        "instrumento eliminado. Se conservan como referencia."),
            "modulo": "precios",
            "parametros": {"isin": h["isin"]},
        })

    resumen = {
        "total": len(pendientes),
        "por_tipo": {},
    }
    for x in pendientes:
        resumen["por_tipo"][x["tipo"]] = resumen["por_tipo"].get(x["tipo"], 0) + 1

    return {"pendientes": pendientes, "estados": estados, "resumen": resumen}
