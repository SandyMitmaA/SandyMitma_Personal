"""Frame 3. Reproceso. Unico modulo que dispara calculo."""
from __future__ import annotations

import json
import time
from datetime import date
from decimal import Decimal
from typing import Any, Optional, Sequence

from aplicacion.casos_uso.contexto import Contexto
from dominio.dinero import CERO, a_texto, dec, q
from dominio.fechas import a_iso, de_iso, rango_fechas
from dominio.valorizacion.corrida import EntradaCorrida, ResultadoCorrida, correr
from infraestructura.persistencia.repo_valorizacion import (
    CAMPOS_COMPARABLES,
    RepoValorizacion,
    fila_a_registro,
)
from infraestructura.persistencia.repositorios import PORTAFOLIO, ahora

ESTADO_PENDIENTE = "pendiente"
ESTADO_EN_PROCESO = "en proceso"
ESTADO_TERMINADO = "terminado"
ESTADO_ERROR = "error"

CAMPO_CLAVE = "total_mv_base"


def _entrada(ctx: Contexto, isines: Sequence[str] | None) -> EntradaCorrida:
    instrumentos = {i.isin: i for i in ctx.instrumentos.listar()}
    posiciones = [p for p in ctx.posiciones.listar() if p.isin in instrumentos]
    if isines:
        posiciones = [p for p in posiciones if p.isin in set(isines)]
    return EntradaCorrida(
        instrumentos=instrumentos,
        posiciones=posiciones,
        precios=ctx.precios.todos(),
        parametros=ctx.parametros.leer(),
    )


def rango_propuesto(ctx: Contexto) -> dict:
    """Rango minimo que cubre todas las fechas marcadas como desactualizadas."""
    filas = ctx.desactualizadas.listar()
    if not filas:
        a, b = ctx.valorizacion.rango_disponible()
        return {"desde": a, "hasta": b, "origen": "ultimo rango valorizado",
                "fechas_desactualizadas": 0, "isines": []}
    fechas = sorted(f["fecha"] for f in filas)
    return {
        "desde": fechas[0],
        "hasta": fechas[-1],
        "origen": "fechas desactualizadas",
        "fechas_desactualizadas": len(filas),
        "isines": sorted({f["isin"] for f in filas}),
    }


def analisis_impacto(ctx: Contexto, desde: date, hasta: date,
                     isines: Sequence[str] | None = None) -> dict:
    p = ctx.parametros.leer()
    desactualizadas = [d for d in ctx.desactualizadas.listar()
                       if a_iso(desde) <= d["fecha"] <= a_iso(hasta)
                       and (not isines or d["isin"] in set(isines))]
    dias = (hasta - desde).days + 1
    posiciones = [x for x in ctx.posiciones.listar()
                  if not isines or x.isin in set(isines)]

    cambios: list[dict] = []
    for r in ctx.bd.consultar(
        "SELECT * FROM bitacora WHERE accion IN ("
        "'ALTA_INSTRUMENTO','EDICION_INSTRUMENTO','ELIMINACION_INSTRUMENTO',"
        "'REACTIVACION_INSTRUMENTO','ALTA_POSICION','EDICION_POSICION',"
        "'ELIMINACION_POSICION','REACTIVACION_POSICION','CARGA_PRECIOS',"
        "'ELIMINACION_PRECIO','CAMBIO_PARAMETROS') "
        "ORDER BY id DESC LIMIT 50"
    ):
        cambios.append({
            "momento": r["momento"], "usuario": r["usuario"], "accion": r["accion"],
            "entidad": r["entidad"], "entidad_id": r["entidad_id"],
        })

    return {
        "desde": a_iso(desde),
        "hasta": a_iso(hasta),
        "dias": dias,
        "isines": list(isines) if isines else [x.isin for x in posiciones],
        "posiciones": len(posiciones),
        "valorizaciones_afectadas": dias * len(posiciones),
        "fechas_desactualizadas": len(desactualizadas),
        "detalle_desactualizadas": desactualizadas[:200],
        "cambios_desde_ultimo_calculo": cambios,
        "periodos_cerrados": ctx.periodos.interseccion(desde, hasta),
        "total_actual_inicio": a_texto(ctx.valorizacion.total_portafolio(desde, p.incluir_caja)),
        "total_actual_fin": a_texto(ctx.valorizacion.total_portafolio(hasta, p.incluir_caja)),
        "incluir_caja": p.incluir_caja,
    }


def encolar(ctx: Contexto, desde: date, hasta: date, isines: Sequence[str] | None,
            usuario: str, disparador: str = "manual", forzado: bool = False,
            justificacion_reapertura: str = "") -> int:
    cerrados = ctx.periodos.interseccion(desde, hasta)
    if cerrados and not justificacion_reapertura.strip():
        raise PermissionError(
            "El rango cae en un periodo cerrado. Se exige reapertura explicita "
            "con justificacion en texto libre."
        )
    if cerrados:
        for c in cerrados:
            ctx.periodos.reabrir(c["id"], usuario, justificacion_reapertura)
        ctx.bitacora.registrar(
            "REAPERTURA_PERIODO", usuario, entidad="periodo",
            entidad_id=",".join(str(c["id"]) for c in cerrados),
            detalle={"justificacion": justificacion_reapertura},
            rango_desde=desde, rango_hasta=hasta,
        )

    cur = ctx.bd.ejecutar(
        "INSERT INTO reproceso (portafolio_id, fecha_desde, fecha_hasta, isines,"
        " disparador, usuario, encolado_en, estado, forzado)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (PORTAFOLIO, a_iso(desde), a_iso(hasta),
         json.dumps(list(isines)) if isines else None,
         disparador, usuario, ahora(), ESTADO_PENDIENTE, 1 if forzado else 0),
    )
    return int(cur.lastrowid)


def ejecutar(ctx: Contexto, reproceso_id: int) -> dict:
    """Transaccional: o se publica el rango entero, o no se publica nada."""
    r = ctx.bd.uno("SELECT * FROM reproceso WHERE id=?", (reproceso_id,))
    if r is None:
        raise ValueError(f"No existe el reproceso {reproceso_id}.")
    desde, hasta = de_iso(r["fecha_desde"]), de_iso(r["fecha_hasta"])
    isines = json.loads(r["isines"]) if r["isines"] else None
    usuario = r["usuario"] or "sistema"
    forzado = bool(r["forzado"])

    t0 = time.time()
    ctx.bd.ejecutar("UPDATE reproceso SET estado=?, iniciado_en=? WHERE id=?",
                    (ESTADO_EN_PROCESO, ahora(), reproceso_id))
    try:
        entrada = _entrada(ctx, isines)
        resultado = correr(entrada, desde, hasta)
        registros = [fila_a_registro(f) for f in resultado.filas]

        anterior = ctx.valorizacion.mapa_vigente(desde, hasta)
        if isines:
            # Reproceso parcial: la version publicada sigue siendo una foto
            # completa del rango, asi que lo no recalculado se arrastra tal cual.
            seleccionados = set(isines)
            for (_fecha, isin), prev in anterior.items():
                if isin not in seleccionados:
                    registros.append(dict(prev))

        diferencias = _diferencias(anterior, registros)
        # Diferencia estructural decide si versionar; cambio de valor decide
        # que entra al reporte de reexpresion.
        reexpresadas = [d for d in diferencias if d["valor_cambio"]]
        sin_cambios = not diferencias and len(anterior) == len(registros)

        if sin_cambios and not forzado:
            # Reejecucion idempotente: no genera version nueva.
            ctx.desactualizadas.limpiar_rango(desde, hasta, isines)
            dur = int((time.time() - t0) * 1000)
            ctx.bd.ejecutar(
                "UPDATE reproceso SET estado=?, terminado_en=?, duracion_ms=?,"
                " valorizaciones_totales=?, valorizaciones_cambiadas=0,"
                " mensaje=? WHERE id=?",
                (ESTADO_TERMINADO, ahora(), dur, len(registros),
                 "Sin diferencias. No se genero version nueva.", reproceso_id),
            )
            ctx.bitacora.registrar(
                "REPROCESO", usuario, entidad="reproceso", entidad_id=str(reproceso_id),
                detalle={"resultado": "sin cambios"},
                rango_desde=desde, rango_hasta=hasta, valorizaciones_cambiadas=0,
            )
            return {"reproceso_id": reproceso_id, "version": None, "cambios": 0,
                    "sin_cambios": True, "procesadas": len(registros)}

        with ctx.bd.transaccion():
            version = ctx.valorizacion.crear_version(reproceso_id, usuario, desde, hasta)
            ctx.valorizacion.publicar(version, registros)
            _guardar_reexpresion(ctx, reproceso_id, reexpresadas, usuario)
            ctx.bd.ejecutar(
                "UPDATE reproceso SET version_calculo=? WHERE id=?", (version, reproceso_id)
            )

        ctx.desactualizadas.limpiar_rango(desde, hasta, isines)
        dur = int((time.time() - t0) * 1000)
        impacto_total = sum((d["diferencia"] for d in reexpresadas), CERO)
        ctx.bd.ejecutar(
            "UPDATE reproceso SET estado=?, terminado_en=?, duracion_ms=?,"
            " valorizaciones_totales=?, valorizaciones_cambiadas=?, mensaje=? WHERE id=?",
            (ESTADO_TERMINADO, ahora(), dur, len(registros), len(reexpresadas),
             f"Impacto total en moneda base: {q(impacto_total, 2)}", reproceso_id),
        )
        ctx.bitacora.registrar(
            "REPROCESO", usuario, entidad="reproceso", entidad_id=str(reproceso_id),
            detalle={"version": version, "impacto_total": a_texto(impacto_total)},
            rango_desde=desde, rango_hasta=hasta, valorizaciones_cambiadas=len(reexpresadas),
        )
        return {"reproceso_id": reproceso_id, "version": version,
                "cambios": len(reexpresadas), "sin_cambios": False,
                "procesadas": len(registros),
                "impacto_total": a_texto(impacto_total)}
    except Exception as e:  # noqa: BLE001
        ctx.bd.ejecutar(
            "UPDATE reproceso SET estado=?, terminado_en=?, mensaje=? WHERE id=?",
            (ESTADO_ERROR, ahora(), f"{type(e).__name__}: {e}", reproceso_id),
        )
        raise


def _diferencias(anterior: dict[tuple[str, str], dict],
                 registros: Sequence[dict]) -> list[dict]:
    difs: list[dict] = []
    for nuevo in registros:
        clave = (nuevo["fecha_valorizacion"], nuevo["isin"])
        prev = anterior.get(clave)
        if prev is None:
            vn = dec(nuevo.get(CAMPO_CLAVE) or 0)
            difs.append({
                "fecha": clave[0], "isin": clave[1],
                "anterior": None, "nuevo": nuevo[CAMPO_CLAVE],
                "diferencia": vn,
                "relativa": None,
                "campos": ["alta de valorizacion"],
                # Una fila que antes no existia y ahora vale cero no reexpresa
                # nada: no hay valor previo que corregir.
                "valor_cambio": vn != 0,
            })
            continue
        distintos = [c for c in CAMPOS_COMPARABLES
                     if _normalizar(prev.get(c)) != _normalizar(nuevo.get(c))]
        if not distintos:
            continue
        va = dec(prev.get(CAMPO_CLAVE) or 0)
        vn = dec(nuevo.get(CAMPO_CLAVE) or 0)
        difs.append({
            "fecha": clave[0], "isin": clave[1],
            "anterior": prev.get(CAMPO_CLAVE), "nuevo": nuevo.get(CAMPO_CLAVE),
            "diferencia": vn - va,
            "relativa": (vn - va) / va if va != 0 else None,
            "campos": distintos,
            "valor_cambio": vn != va,
        })
    faltantes = set(anterior) - {(r["fecha_valorizacion"], r["isin"]) for r in registros}
    for clave in sorted(faltantes):
        prev = anterior[clave]
        va = dec(prev.get(CAMPO_CLAVE) or 0)
        difs.append({
            "fecha": clave[0], "isin": clave[1],
            "anterior": prev.get(CAMPO_CLAVE), "nuevo": None,
            "diferencia": -va, "relativa": dec(-1) if va != 0 else None,
            "campos": ["baja de valorizacion"],
            "valor_cambio": va != 0,
        })
    difs.sort(key=lambda d: (d["fecha"], d["isin"]))
    return difs


def _normalizar(v: Any) -> Any:
    if v is None or v == "":
        return None
    if isinstance(v, (int,)):
        return str(v)
    s = str(v)
    try:
        return format(dec(s).normalize(), "f")
    except Exception:  # noqa: BLE001
        return s


def _causa(campos: Sequence[str]) -> str:
    if "alta de valorizacion" in campos:
        return "Alta de instrumento o posicion"
    if "baja de valorizacion" in campos:
        return "Eliminacion de instrumento o posicion"
    if "nominal" in campos:
        return "Cambio de nominal"
    if any(c in campos for c in ("precio_proveedor", "precio_local", "precio_imputado")):
        return "Precio"
    if any(c in campos for c in ("tipo_cambio", "tipo_cambio_imputado")):
        return "Tipo de cambio"
    if any(c in campos for c in ("fecha_devengo", "dias_transcurridos", "dias_periodo",
                                 "devengo_por_100", "cupon_por_periodo")):
        return "Parametro o convencion de devengo"
    if "vigente" in campos:
        return "Cambio de fecha de alta o de vigencia"
    return "Recalculo"


def _guardar_reexpresion(ctx: Contexto, reproceso_id: int, difs: Sequence[dict],
                         usuario: str) -> None:
    momento = ahora()
    ctx.bd.ejecutar_muchos(
        "INSERT INTO reexpresion (reproceso_id, fecha_valorizacion, isin, campo,"
        " valor_anterior, valor_nuevo, diferencia_absoluta, diferencia_relativa,"
        " causa, usuario, momento) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            (reproceso_id, d["fecha"], d["isin"], CAMPO_CLAVE, d["anterior"], d["nuevo"],
             a_texto(d["diferencia"]),
             a_texto(d["relativa"]) if d["relativa"] is not None else None,
             _causa(d["campos"]), usuario, momento)
            for d in difs
        ],
    )


def listar_reprocesos(ctx: Contexto, limite: int = 100) -> list[dict]:
    return [dict(r) for r in ctx.bd.consultar(
        "SELECT * FROM reproceso ORDER BY id DESC LIMIT ?", (limite,))]


def reporte_reexpresion(ctx: Contexto, reproceso_id: int) -> list[dict]:
    return [dict(r) for r in ctx.bd.consultar(
        "SELECT * FROM reexpresion WHERE reproceso_id=? ORDER BY fecha_valorizacion, isin",
        (reproceso_id,))]
