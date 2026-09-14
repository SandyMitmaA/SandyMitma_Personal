"""Panel de validaciones. Seccion 11. Las trece comprobaciones, recalculadas siempre."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from aplicacion.casos_uso.contexto import Contexto
from aplicacion.casos_uso.estado import rango_obligatorio
from dominio.configuracion import PRECIO_EN_BASE
from dominio.control.control_t0 import REVISAR
from dominio.dinero import CERO, a_texto, dec, q
from dominio.fechas import a_iso, de_iso, es_dia_habil, rango_fechas
from dominio.modelos import ESTADO_VALORIZADO
from dominio.valorizacion.calendario import calendario_cupones
from dominio.valorizacion.convenciones import convencion_de_mercado_sugerida

OK = "ok"
WARN = "warn"
ALERT = "alert"


def _v(codigo: str, titulo: str, nivel: str, n: int, detalle: list) -> dict:
    return {"codigo": codigo, "titulo": titulo,
            "nivel": OK if n == 0 else nivel, "hallazgos": n, "detalle": detalle[:200]}


def panel(ctx: Contexto, desde: Optional[date] = None,
          hasta: Optional[date] = None) -> dict:
    p = ctx.parametros.leer()
    a, b = ctx.valorizacion.rango_disponible()
    desde = desde or (de_iso(a) if a else p.fecha_inicio_portafolio)
    hasta = hasta or (de_iso(b) if b else p.fecha_inicio_portafolio)
    filas = ctx.valorizacion.vigentes(desde, hasta)
    instrumentos = {i.isin: i for i in ctx.instrumentos.listar()}
    posiciones = ctx.posiciones.listar()
    hoy = date.today()
    checks: list[dict] = []

    # 1. Registros de precio duplicados por fecha e instrumento.
    dup = [dict(r) for r in ctx.bd.consultar(
        "SELECT fecha, isin, COUNT(*) n FROM precio WHERE eliminado_en IS NULL "
        "GROUP BY fecha, isin HAVING COUNT(*) > 1")]
    checks.append(_v("1", "Registros de precio duplicados por fecha e instrumento",
                     ALERT, len(dup), dup))

    # 2. Tipo de cambio en cero o ausente, e imputados.
    tc_cero = [dict(r) for r in ctx.bd.consultar(
        "SELECT fecha, isin, tipo_cambio FROM precio WHERE eliminado_en IS NULL "
        "AND (tipo_cambio IS NULL OR tipo_cambio='' OR CAST(tipo_cambio AS REAL)=0) "
        "ORDER BY fecha")]
    tc_imputado = [{"fecha": f["fecha_valorizacion"], "isin": f["isin"],
                    "origen": f["fecha_origen_tipo_cambio"], "tipo_cambio": f["tipo_cambio"]}
                   for f in filas if f["tipo_cambio_imputado"]]
    checks.append(_v("2", "Fechas con tipo de cambio en cero o ausente, y cuales se imputaron",
                     WARN, len(tc_cero) + len(tc_imputado), tc_cero + tc_imputado))

    # 3. Fechas vigentes sin precio, y cuantas se resolvieron por arrastre.
    arrastre = [{"fecha": f["fecha_valorizacion"], "isin": f["isin"],
                 "dias": f["dias_arrastre_precio"], "origen": f["fecha_origen_precio"]}
                for f in filas if f["precio_imputado"]]
    sin_precio = [{"fecha": f["fecha_valorizacion"], "isin": f["isin"], "error": f["error"]}
                  for f in filas if f["vigente"] and (f["error"] or "")]
    checks.append(_v("3", "Fechas vigentes sin precio y resueltas por arrastre",
                     WARN if not sin_precio else ALERT,
                     len(arrastre) + len(sin_precio), sin_precio + arrastre))

    # 4. Precio implicito en moneda local fuera de rango razonable.
    fuera: list[dict] = []
    for f in filas:
        pl = f["precio_local"]
        if not pl or not f["vigente"]:
            continue
        v = dec(pl)
        if not (p.precio_local_min_razonable <= v <= p.precio_local_max_razonable):
            instr = instrumentos.get(f["isin"])
            fuera.append({
                "fecha": f["fecha_valorizacion"], "isin": f["isin"],
                "precio_local": pl, "moneda": instr.moneda if instr else "",
                "precio_expresado_en": instr.precio_expresado_en if instr else "",
                "nota": ("Delata que el precio llega ya convertido cuando la maestra "
                         "dice lo contrario, o al reves."),
            })
    checks.append(_v("4", "Precio implicito en moneda local fuera de rango razonable",
                     ALERT, len(fuera), fuera))

    # 5. Instrumentos que vencen sin precio en la fecha de vencimiento.
    venc: list[dict] = []
    for pos in posiciones:
        instr = instrumentos.get(pos.isin)
        if instr is None or instr.fecha_vencimiento > hoy:
            continue
        tiene = any(x.fecha == instr.fecha_vencimiento and x.precio is not None
                    for x in ctx.precios.por_instrumento(pos.isin))
        if not tiene:
            cupon = dec(instr.tasa_cupon) / dec(instr.frecuencia)
            redencion = dec(pos.nominal) * (dec(1) + cupon / dec(100))
            ultima = _ultima_valorizacion_mercado(ctx, pos.isin, instr.fecha_vencimiento)
            venc.append({
                "isin": pos.isin,
                "fecha_vencimiento": a_iso(instr.fecha_vencimiento),
                "valor_redencion": a_texto(q(redencion, p.decimales_monto)),
                "ultima_valorizacion_mercado": a_texto(q(ultima["valor"], p.decimales_monto))
                if ultima else None,
                "fecha_ultima_valorizacion": ultima["fecha"] if ultima else None,
                "diferencia": a_texto(q(redencion - ultima["valor"], p.decimales_monto))
                if ultima else None,
                "nota": "La diferencia se reporta, no se absorbe en silencio.",
            })
    checks.append(_v("5", "Instrumentos que vencen sin precio en la fecha de vencimiento",
                     WARN, len(venc), venc))

    # 6. Fechas de valorizacion en dia no habil.
    no_habiles = sorted({f["fecha_valorizacion"] for f in filas
                         if not es_dia_habil(de_iso(f["fecha_valorizacion"]))})
    checks.append(_v("6", "Fechas de valorizacion en dia no habil", WARN,
                     len(no_habiles), [{"fecha": f} for f in no_habiles]))

    # 7. Convenciones de la maestra desviadas del uso de mercado, con impacto.
    desviaciones: list[dict] = []
    for isin, instr in instrumentos.items():
        sugerida = convencion_de_mercado_sugerida(instr.moneda)
        if not sugerida or sugerida == instr.convencion:
            continue
        impacto = _impacto_convencion(ctx, isin, instr, sugerida, hasta)
        desviaciones.append({
            "isin": isin, "moneda": instr.moneda, "declarada": instr.convencion,
            "uso_de_mercado": sugerida,
            "impacto_moneda_base": a_texto(q(impacto, p.decimales_monto))
            if impacto is not None else None,
            "nota": "Informativo. El motor no altera la convencion de la maestra.",
        })
    checks.append(_v("7", "Convenciones de la maestra desviadas del uso de mercado",
                     WARN, len(desviaciones), desviaciones))

    # 8. Fechas con estado Revisar.
    revisar = _fechas_revisar(ctx, filas, p)
    checks.append(_v("8", "Fechas con estado Revisar en el control T+0",
                     ALERT, len(revisar), revisar))

    # 9. Filas donde el control del puente no da cero.
    rotas = [{"fecha": f["fecha_valorizacion"], "isin": f["isin"], "control": f["control"]}
             for f in filas if f["control"] and abs(dec(f["control"])) > p.tolerancia_quiebre]
    checks.append(_v("9", "Filas donde el control del puente no da cero",
                     ALERT, len(rotas), rotas))

    # 10. Posiciones con huecos en su serie de precios.
    huecos: list[dict] = []
    for pos in posiciones:
        instr = instrumentos.get(pos.isin)
        if instr is None:
            continue
        d, h = rango_obligatorio(instr, pos, hoy)
        tiene = {x.fecha for x in ctx.precios.por_instrumento(pos.isin) if x.precio is not None}
        faltan = [a_iso(f) for f in rango_fechas(d, h) if f not in tiene]
        if faltan:
            huecos.append({"isin": pos.isin, "desde": a_iso(d), "hasta": a_iso(h),
                           "faltantes": len(faltan), "primeras": faltan[:20]})
    checks.append(_v("10", "Posiciones con huecos en su serie de precios entre alta y hoy",
                     WARN, len(huecos), huecos))

    # 11. Valorizaciones con version posterior a la publicada.
    pendientes_comunicar = [dict(r) for r in ctx.bd.consultar(
        "SELECT r.id AS reproceso_id, r.terminado_en, COUNT(x.id) AS filas "
        "FROM reproceso r JOIN reexpresion x ON x.reproceso_id = r.id "
        "GROUP BY r.id ORDER BY r.id DESC LIMIT 20")]
    checks.append(_v("11", "Reexpresiones pendientes de comunicar", WARN,
                     len(pendientes_comunicar), pendientes_comunicar))

    # 12. Eliminados con valorizaciones aun vigentes.
    elim = [dict(r) for r in ctx.bd.consultar(
        "SELECT p.id, p.isin, p.motivo_eliminacion FROM posicion p "
        "WHERE p.eliminado_en IS NOT NULL AND EXISTS (SELECT 1 FROM valorizacion_vigente v "
        "WHERE v.posicion_id = p.id AND v.vigente = 1)")]
    checks.append(_v("12", "Instrumentos o posiciones eliminados con valorizaciones vigentes",
                     ALERT, len(elim), elim))

    # 13. Series de precios huerfanas.
    huerfanos = ctx.precios.huerfanos()
    checks.append(_v("13", "Series de precios huerfanas de instrumentos eliminados",
                     WARN, len(huerfanos), huerfanos))

    return {
        "desde": a_iso(desde), "hasta": a_iso(hasta),
        "validaciones": checks,
        "resumen": {
            "alertas": sum(1 for c in checks if c["nivel"] == ALERT),
            "advertencias": sum(1 for c in checks if c["nivel"] == WARN),
            "conformes": sum(1 for c in checks if c["nivel"] == OK),
        },
    }


def _ultima_valorizacion_mercado(ctx: Contexto, isin: str,
                                 vencimiento: date) -> Optional[dict]:
    """Ultima fecha con precio observado antes del vencimiento, a convencion de mercado."""
    r = ctx.bd.uno(
        "SELECT fecha_valorizacion, total_mv_base_t0, total_mv_base FROM valorizacion_vigente "
        "WHERE isin=? AND vigente=1 AND fecha_valorizacion < ? "
        "ORDER BY fecha_valorizacion DESC LIMIT 1",
        (isin, a_iso(vencimiento)),
    )
    if r is None:
        return None
    valor = r["total_mv_base_t0"] or r["total_mv_base"]
    return {"fecha": r["fecha_valorizacion"], "valor": dec(valor or 0)}


def _fechas_revisar(ctx: Contexto, filas: list[dict], p) -> list[dict]:
    from dominio.control.control_t0 import clasificar_quiebre

    por_fecha: dict[str, dict[str, Decimal]] = {}
    for f in filas:
        d = por_fecha.setdefault(f["fecha_valorizacion"], {"q": CERO, "d": CERO})
        d["q"] += dec(f["quiebre_t0"] or 0)
        d["d"] += dec(f["devengo_diario"] or 0)
    salida = []
    for fecha, d in sorted(por_fecha.items()):
        estado, residual = clasificar_quiebre(d["q"], d["d"], p.tolerancia_quiebre)
        if estado == REVISAR:
            salida.append({"fecha": fecha, "quiebre": a_texto(q(d["q"], 2)),
                           "devengo_diario": a_texto(q(d["d"], 2)),
                           "residual": a_texto(q(residual, 2)), "estado": estado})
    return salida


def _impacto_convencion(ctx: Contexto, isin: str, instr, sugerida: str,
                        fecha: date) -> Optional[Decimal]:
    """Cuantifica en moneda base la diferencia entre la convencion declarada y la de mercado."""
    import dataclasses

    from dominio.modelos import DatoMercado
    from dominio.valorizacion.motor import valorizar
    from dominio.valorizacion.series import SeriePrecios

    p = ctx.parametros.leer()
    pos = next((x for x in ctx.posiciones.listar() if x.isin == isin), None)
    if pos is None:
        return None
    serie = SeriePrecios(ctx.precios.por_instrumento(isin))
    mercado = serie.resolver(fecha, p.dias_max_arrastre)
    if mercado.precio is None:
        return None
    cal = calendario_cupones(instr.fecha_emision, instr.fecha_vencimiento, instr.frecuencia)
    a = valorizar(instr, pos, fecha, mercado, p, cal)
    b = valorizar(dataclasses.replace(instr, convencion=sugerida), pos, fecha, mercado, p, cal)
    return b.total_mv_base - a.total_mv_base
