"""Frame 1. Registro de instrumentos y posiciones. No dispara calculos."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from aplicacion.casos_uso.contexto import Contexto
from dominio.configuracion import (
    CONVENCIONES,
    PRECIO_EN_BASE,
    PRECIO_EN_LOCAL,
)
from dominio.dinero import a_texto, dec
from dominio.fechas import a_iso, de_iso, rango_fechas
from dominio.modelos import Instrumento, Posicion
from dominio.valorizacion.calendario import calendario_cupones
from dominio.valorizacion.convenciones import convencion_de_mercado_sugerida

FRECUENCIAS_VALIDAS = (1, 2, 3, 4, 6, 12)


class ErrorValidacion(ValueError):
    def __init__(self, campo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.campo = campo
        self.mensaje = mensaje


def validar_maestra(d: dict[str, Any]) -> Instrumento:
    isin = (d.get("isin") or "").strip().upper()
    if len(isin) != 12 or not isin.isalnum():
        raise ErrorValidacion("isin", "El ISIN debe tener 12 caracteres alfanumericos.")
    moneda = (d.get("moneda") or "").strip().upper()
    if len(moneda) != 3:
        raise ErrorValidacion("moneda", "La moneda debe ser un codigo ISO de 3 letras.")
    try:
        tasa = dec(str(d.get("tasa_cupon")))
    except (InvalidOperation, TypeError):
        raise ErrorValidacion("tasa_cupon", "La tasa de cupon no es un numero valido.")
    if tasa < 0:
        raise ErrorValidacion("tasa_cupon", "La tasa de cupon no puede ser negativa.")
    try:
        frecuencia = int(d.get("frecuencia"))
    except (TypeError, ValueError):
        raise ErrorValidacion("frecuencia", "La frecuencia no es un entero valido.")
    if frecuencia not in FRECUENCIAS_VALIDAS:
        raise ErrorValidacion(
            "frecuencia",
            f"La frecuencia debe ser una de {', '.join(map(str, FRECUENCIAS_VALIDAS))}.",
        )
    emision = de_iso(d.get("fecha_emision"))
    vencimiento = de_iso(d.get("fecha_vencimiento"))
    if emision is None:
        raise ErrorValidacion("fecha_emision", "Falta la fecha de emision.")
    if vencimiento is None:
        raise ErrorValidacion("fecha_vencimiento", "Falta la fecha de vencimiento.")
    if vencimiento <= emision:
        raise ErrorValidacion(
            "fecha_vencimiento", "El vencimiento debe ser posterior a la emision."
        )
    convencion = (d.get("convencion") or "").strip().upper()
    if convencion not in CONVENCIONES:
        raise ErrorValidacion(
            "convencion", f"Convencion no soportada. Use una de {', '.join(CONVENCIONES)}."
        )
    precio_en = (d.get("precio_expresado_en") or PRECIO_EN_LOCAL).strip().upper()
    if precio_en not in (PRECIO_EN_LOCAL, PRECIO_EN_BASE):
        raise ErrorValidacion("precio_expresado_en", "Debe ser LOCAL o BASE.")
    try:
        redencion = dec(str(d.get("valor_redencion") or "100"))
    except (InvalidOperation, TypeError):
        raise ErrorValidacion("valor_redencion", "El valor de redencion no es valido.")

    return Instrumento(
        isin=isin, moneda=moneda, tasa_cupon=tasa, frecuencia=frecuencia,
        fecha_emision=emision, fecha_vencimiento=vencimiento, convencion=convencion,
        precio_expresado_en=precio_en, valor_redencion=redencion,
        descripcion=(d.get("descripcion") or "").strip(),
    )


def guardar_instrumento(ctx: Contexto, datos: dict, usuario: str) -> dict:
    instr = validar_maestra(datos)
    existia = ctx.instrumentos.obtener(instr.isin)
    ctx.instrumentos.guardar(instr, usuario)
    cal = calendario_cupones(instr.fecha_emision, instr.fecha_vencimiento, instr.frecuencia)
    ctx.instrumentos.guardar_calendario(instr.isin, cal)
    ctx.bitacora.registrar(
        "ALTA_INSTRUMENTO" if not existia else "EDICION_INSTRUMENTO",
        usuario, entidad="instrumento", entidad_id=instr.isin,
        detalle={"maestra": datos},
    )

    afectadas = 0
    if existia:
        afectadas = _marcar_afectadas_por_instrumento(ctx, instr.isin, "Maestra modificada")

    sugerida = convencion_de_mercado_sugerida(instr.moneda)
    return {
        "isin": instr.isin,
        "calendario": [a_iso(f) for f in cal],
        "editado": bool(existia),
        "fechas_desactualizadas": afectadas,
        "desviacion_convencion": (
            None if not sugerida or sugerida == instr.convencion
            else {"declarada": instr.convencion, "uso_de_mercado": sugerida}
        ),
    }


def previsualizar_calendario(datos: dict) -> dict:
    instr = validar_maestra(datos)
    cal = calendario_cupones(instr.fecha_emision, instr.fecha_vencimiento, instr.frecuencia)
    return {
        "isin": instr.isin,
        "calendario": [a_iso(f) for f in cal],
        "cupon_por_periodo": a_texto(instr.tasa_cupon / dec(instr.frecuencia)),
    }


def guardar_posicion(ctx: Contexto, datos: dict, usuario: str) -> dict:
    isin = (datos.get("isin") or "").strip().upper()
    instr = ctx.instrumentos.obtener(isin)
    if instr is None or instr.eliminado_en:
        raise ErrorValidacion("isin", f"No existe un instrumento activo con ISIN {isin}.")
    try:
        nominal = dec(str(datos.get("nominal")))
    except (InvalidOperation, TypeError):
        raise ErrorValidacion("nominal", "El nominal no es un numero valido.")
    if nominal <= 0:
        raise ErrorValidacion("nominal", "El nominal debe ser mayor que cero.")
    fecha_alta = de_iso(datos.get("fecha_alta"))
    if fecha_alta is None:
        raise ErrorValidacion("fecha_alta", "Falta la fecha de alta en cartera.")
    # Seccion 6.1
    if fecha_alta > instr.fecha_vencimiento:
        raise ErrorValidacion(
            "fecha_alta",
            f"La fecha de alta {a_iso(fecha_alta)} es posterior al vencimiento "
            f"{a_iso(instr.fecha_vencimiento)}. El registro se rechaza.",
        )

    id_existente = datos.get("id")
    pos = Posicion(id=int(id_existente) if id_existente else 0, isin=isin,
                   nominal=nominal, fecha_alta=fecha_alta)
    nuevo_id = ctx.posiciones.guardar(pos, usuario)

    p = ctx.parametros.leer()
    if id_existente:
        afectadas = _marcar_afectadas_por_instrumento(ctx, isin, "Posicion modificada")
    else:
        afectadas = _marcar_afectadas_por_alta(ctx, isin, fecha_alta, instr.fecha_vencimiento)

    hoy = date.today()
    hasta = min(hoy, instr.fecha_vencimiento)
    precios = {x.fecha for x in ctx.precios.por_instrumento(isin) if x.precio is not None}
    faltantes = [a_iso(f) for f in rango_fechas(fecha_alta, hasta) if f not in precios]

    ctx.bitacora.registrar(
        "ALTA_POSICION" if not id_existente else "EDICION_POSICION", usuario,
        entidad="posicion", entidad_id=str(nuevo_id),
        detalle={"isin": isin, "nominal": str(nominal), "fecha_alta": a_iso(fecha_alta)},
    )

    return {
        "posicion_id": nuevo_id,
        "isin": isin,
        "parte_del_saldo_inicial": fecha_alta <= p.fecha_inicio_portafolio,
        "genera_alta_en_puente": fecha_alta > p.fecha_inicio_portafolio,
        "rango_precios_desde": a_iso(fecha_alta),
        "rango_precios_hasta": a_iso(hasta),
        "fechas_faltantes_total": len(faltantes),
        "fechas_faltantes": faltantes[:60],
        "fechas_desactualizadas": afectadas,
    }


def _marcar_afectadas_por_alta(ctx: Contexto, isin: str, fecha_alta: date,
                               vencimiento: date) -> int:
    """Un alta retroactiva desactualiza todo lo ya valorizado desde su fecha de alta.

    El rango se acota al ultimo dia que el portafolio tiene valorizado: mas alla
    de ahi no hay nada calculado que quede obsoleto.
    """
    _, ultima = ctx.valorizacion.rango_disponible()
    if not ultima:
        return 0
    hasta = min(de_iso(ultima), vencimiento)
    if hasta < fecha_alta:
        return 0
    return ctx.desactualizadas.marcar(
        rango_fechas(fecha_alta, hasta), isin, "Alta de posicion"
    )


def _marcar_afectadas_por_instrumento(ctx: Contexto, isin: str, motivo: str) -> int:
    """La edicion nunca recalcula: marca y deja visible en la bandeja."""
    fechas = ctx.valorizacion.fechas_con_valorizacion(isin)
    if not fechas:
        return 0
    return ctx.desactualizadas.marcar([de_iso(f) for f in fechas], isin, motivo)


# --- Seccion 6.2. Eliminacion logica con analisis de impacto ---------------

def impacto_eliminacion_posicion(ctx: Contexto, id_posicion: int) -> dict:
    pos = ctx.posiciones.obtener(id_posicion)
    if pos is None:
        raise ErrorValidacion("id", f"No existe la posicion {id_posicion}.")
    p = ctx.parametros.leer()
    fechas = ctx.valorizacion.fechas_con_valorizacion(pos.isin)
    fechas = [f for f in fechas if de_iso(f) >= pos.fecha_alta]
    desde = de_iso(fechas[0]) if fechas else pos.fecha_alta
    hasta = de_iso(fechas[-1]) if fechas else pos.fecha_alta

    def total_sin(f: date) -> Decimal:
        filas = ctx.valorizacion.vigentes(f, f)
        total = dec(0)
        for r in filas:
            if r["posicion_id"] == id_posicion:
                continue
            total += dec(r["total_mv_base"] or 0)
            if p.incluir_caja:
                total += dec(r["caja_base"] or 0)
        return total

    cerrados = ctx.periodos.interseccion(desde, hasta) if fechas else []
    return {
        "posicion_id": id_posicion,
        "isin": pos.isin,
        "nominal": str(pos.nominal),
        "fecha_alta": a_iso(pos.fecha_alta),
        "rango_valorizado_desde": fechas[0] if fechas else None,
        "rango_valorizado_hasta": fechas[-1] if fechas else None,
        "valorizaciones_afectadas": len(fechas),
        "parte_del_saldo_inicial": pos.fecha_alta <= p.fecha_inicio_portafolio,
        "total_actual_inicio": a_texto(ctx.valorizacion.total_portafolio(desde, p.incluir_caja)) if fechas else None,
        "total_resultante_inicio": a_texto(total_sin(desde)) if fechas else None,
        "total_actual_fin": a_texto(ctx.valorizacion.total_portafolio(hasta, p.incluir_caja)) if fechas else None,
        "total_resultante_fin": a_texto(total_sin(hasta)) if fechas else None,
        "periodos_cerrados": cerrados,
    }


def eliminar_posicion(ctx: Contexto, id_posicion: int, motivo: str, usuario: str) -> dict:
    if not motivo or not motivo.strip():
        raise ErrorValidacion("motivo", "El motivo de eliminacion es obligatorio.")
    pos = ctx.posiciones.obtener(id_posicion)
    if pos is None:
        raise ErrorValidacion("id", f"No existe la posicion {id_posicion}.")
    impacto = impacto_eliminacion_posicion(ctx, id_posicion)
    ctx.posiciones.eliminar(id_posicion, usuario, motivo)
    fechas = [de_iso(f) for f in ctx.valorizacion.fechas_con_valorizacion(pos.isin)
              if de_iso(f) >= pos.fecha_alta]
    n = ctx.desactualizadas.marcar(fechas, pos.isin, "Posicion eliminada") if fechas else 0
    ctx.bitacora.registrar(
        "ELIMINACION_POSICION", usuario, entidad="posicion", entidad_id=str(id_posicion),
        detalle={"isin": pos.isin, "motivo": motivo, "impacto": impacto},
        rango_desde=fechas[0] if fechas else None,
        rango_hasta=fechas[-1] if fechas else None,
    )
    # La eliminacion no recalcula: envia a la bandeja de pendientes.
    return {"eliminada": True, "fechas_desactualizadas": n, "impacto": impacto}


def reactivar_posicion(ctx: Contexto, id_posicion: int, usuario: str) -> dict:
    fila = ctx.posiciones.fila(id_posicion)
    if fila is None:
        raise ErrorValidacion("id", f"No existe la posicion {id_posicion}.")
    pos = ctx.posiciones.obtener(id_posicion)
    ctx.posiciones.reactivar(id_posicion, usuario)
    fechas = [de_iso(f) for f in ctx.valorizacion.fechas_con_valorizacion(pos.isin)
              if de_iso(f) >= pos.fecha_alta]
    if not fechas:
        fechas = list(rango_fechas(pos.fecha_alta, date.today()))
    n = ctx.desactualizadas.marcar(fechas, pos.isin, "Posicion reactivada")
    ctx.bitacora.registrar(
        "REACTIVACION_POSICION", usuario, entidad="posicion", entidad_id=str(id_posicion),
        detalle={"isin": pos.isin},
    )
    return {"reactivada": True, "fechas_desactualizadas": n}


def impacto_eliminacion_instrumento(ctx: Contexto, isin: str) -> dict:
    instr = ctx.instrumentos.obtener(isin)
    if instr is None:
        raise ErrorValidacion("isin", f"No existe el instrumento {isin}.")
    posiciones = ctx.posiciones.por_instrumento(isin)
    return {
        "isin": isin,
        "posiciones_activas": [
            {"id": p.id, "nominal": str(p.nominal), "fecha_alta": a_iso(p.fecha_alta)}
            for p in posiciones
        ],
        "requiere_cascada": len(posiciones) > 0,
        "impactos": [impacto_eliminacion_posicion(ctx, p.id) for p in posiciones],
        "precios_conservados": len(ctx.precios.por_instrumento(isin)),
    }


def eliminar_instrumento(ctx: Contexto, isin: str, motivo: str, usuario: str,
                         cascada: bool = False) -> dict:
    if not motivo or not motivo.strip():
        raise ErrorValidacion("motivo", "El motivo de eliminacion es obligatorio.")
    posiciones = ctx.posiciones.por_instrumento(isin)
    if posiciones and not cascada:
        raise ErrorValidacion(
            "cascada",
            f"{isin} tiene {len(posiciones)} posicion(es) asociada(s). Elimina primero "
            "las posiciones o confirma la eliminacion en cascada.",
        )
    total = 0
    for p in posiciones:
        total += eliminar_posicion(ctx, p.id, motivo, usuario)["fechas_desactualizadas"]
    ctx.instrumentos.eliminar(isin, usuario, motivo)
    ctx.bitacora.registrar(
        "ELIMINACION_INSTRUMENTO", usuario, entidad="instrumento", entidad_id=isin,
        detalle={"motivo": motivo, "cascada": cascada,
                 "posiciones": [p.id for p in posiciones]},
    )
    # La serie de precios no se elimina: queda como referencia huerfana.
    return {"eliminado": True, "posiciones_eliminadas": len(posiciones),
            "fechas_desactualizadas": total,
            "precios_conservados": len(ctx.precios.por_instrumento(isin))}


def reactivar_instrumento(ctx: Contexto, isin: str, usuario: str) -> dict:
    ctx.instrumentos.reactivar(isin, usuario)
    ctx.bitacora.registrar("REACTIVACION_INSTRUMENTO", usuario,
                           entidad="instrumento", entidad_id=isin)
    return {"reactivado": True}
