"""Frame 2. Carga de precios. Independiente del registro y del reproceso."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Sequence

from aplicacion.casos_uso.contexto import Contexto
from aplicacion.casos_uso.registro import ErrorValidacion
from dominio.configuracion import PRECIO_EN_BASE
from dominio.dinero import CERO, a_texto, dec, q
from dominio.fechas import a_iso, de_iso, rango_fechas
from infraestructura.archivos.parseo import (
    ErrorArchivo,
    leer,
    normalizar_fecha,
    normalizar_numero,
)
from infraestructura.persistencia.repositorios import ahora

FILA_NUEVA = "nueva"
FILA_IDENTICA = "identica"
FILA_CONFLICTO = "conflicto"
FILA_RECHAZADA = "rechazada"


def clave_idempotencia(nombre: str, contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def _dec_o_none(s: str) -> Optional[Decimal]:
    s = normalizar_numero(s)
    if s == "":
        return None
    try:
        return dec(s)
    except (InvalidOperation, ValueError):
        raise ValueError(f"'{s}' no es un numero valido")


def previsualizar(ctx: Contexto, nombre: str, contenido: bytes,
                  isin_forzado: str = "") -> dict:
    """Preview obligatorio antes de confirmar. Seccion 7."""
    registros, _ = leer(nombre, contenido)
    p = ctx.parametros.leer()
    instrumentos = {i.isin: i for i in ctx.instrumentos.listar()}
    existentes = {
        (a_iso(x.fecha), isin): x
        for isin, serie in ctx.precios.todos().items()
        for x in serie
    }

    vistos: dict[tuple[str, str], int] = {}
    filas: list[dict] = []
    duplicados_internos: list[dict] = []

    for n, r in enumerate(registros, start=1):
        fila: dict[str, Any] = {"linea": n, "estado": FILA_NUEVA, "mensajes": []}
        isin = (isin_forzado or r.get("isin") or "").strip().upper()
        fecha_txt = normalizar_fecha(r.get("fecha", ""))
        fila["isin"] = isin
        fila["fecha"] = fecha_txt
        fila["precio"] = normalizar_numero(r.get("precio", ""))
        fila["tipo_cambio"] = normalizar_numero(r.get("tipo_cambio", ""))
        fila["fuente"] = (r.get("fuente") or nombre).strip()

        f = de_iso(fecha_txt) if fecha_txt else None
        if f is None:
            fila["estado"] = FILA_RECHAZADA
            fila["mensajes"].append(
                f"Linea {n}: la fecha '{r.get('fecha','')}' no es interpretable. "
                "Usa aaaa-mm-dd o dd/mm/aaaa."
            )
        if not isin:
            fila["estado"] = FILA_RECHAZADA
            fila["mensajes"].append(f"Linea {n}: falta el ISIN.")
        instr = instrumentos.get(isin)
        if isin and instr is None:
            fila["mensajes"].append(
                f"Linea {n}: {isin} no esta en la maestra. El precio se guarda "
                "como serie de referencia y quedara marcado como huerfano."
            )
        try:
            precio = _dec_o_none(fila["precio"])
        except ValueError as e:
            precio = None
            fila["estado"] = FILA_RECHAZADA
            fila["mensajes"].append(f"Linea {n}: precio invalido, {e}.")
        try:
            tc = _dec_o_none(fila["tipo_cambio"])
        except ValueError as e:
            tc = None
            fila["estado"] = FILA_RECHAZADA
            fila["mensajes"].append(f"Linea {n}: tipo de cambio invalido, {e}.")

        if tc is None or tc == CERO:
            fila["tipo_cambio_en_cero"] = True
            fila["mensajes"].append(
                f"Linea {n}: tipo de cambio ausente o en cero. Se arrastrara el "
                "ultimo valor habil y el dato quedara marcado como imputado."
            )
        else:
            fila["tipo_cambio_en_cero"] = False

        # Precio implicito en moneda local, para confirmar la moneda declarada.
        if instr is not None and precio is not None and tc not in (None, CERO):
            implicito = (precio * tc if instr.precio_expresado_en == PRECIO_EN_BASE
                         else precio)
            fila["precio_local_implicito"] = a_texto(q(implicito, p.decimales_precio))
            fila["precio_expresado_en"] = instr.precio_expresado_en
            if not (p.precio_local_min_razonable <= implicito <= p.precio_local_max_razonable):
                fila["mensajes"].append(
                    f"Linea {n}: el precio implicito en {instr.moneda} es "
                    f"{q(implicito, 4)}, fuera del rango razonable "
                    f"[{p.precio_local_min_razonable}, {p.precio_local_max_razonable}]. "
                    "Revisa si la maestra declara bien la moneda del precio."
                )

        clave = (fecha_txt, isin)
        if fila["estado"] != FILA_RECHAZADA:
            if clave in vistos:
                fila["estado"] = FILA_RECHAZADA
                fila["mensajes"].append(
                    f"Linea {n}: duplicado dentro del propio archivo "
                    f"(ya aparece en la linea {vistos[clave]}). La carga rechaza "
                    "duplicados, no los suma."
                )
                duplicados_internos.append({"linea": n, "primera": vistos[clave],
                                            "fecha": fecha_txt, "isin": isin})
            else:
                vistos[clave] = n
                previo = existentes.get(clave)
                if previo is not None:
                    mismo = (a_texto(previo.precio) == a_texto(precio)
                             and a_texto(previo.tipo_cambio) == a_texto(tc))
                    fila["estado"] = FILA_IDENTICA if mismo else FILA_CONFLICTO
                    fila["precio_anterior"] = a_texto(previo.precio)
                    fila["tipo_cambio_anterior"] = a_texto(previo.tipo_cambio)

        filas.append(fila)

    cobertura = _cobertura_resultante(ctx, filas)
    resumen = {
        "nuevas": sum(1 for f in filas if f["estado"] == FILA_NUEVA),
        "identicas": sum(1 for f in filas if f["estado"] == FILA_IDENTICA),
        "conflicto": sum(1 for f in filas if f["estado"] == FILA_CONFLICTO),
        "rechazadas": sum(1 for f in filas if f["estado"] == FILA_RECHAZADA),
        "tipo_cambio_en_cero": sum(1 for f in filas if f.get("tipo_cambio_en_cero")),
        "duplicados_internos": len(duplicados_internos),
        "total": len(filas),
    }
    clave = clave_idempotencia(nombre, contenido)
    ya_cargado = ctx.bd.uno("SELECT * FROM carga WHERE clave_idempotencia=?", (clave,))
    return {
        "clave_idempotencia": clave,
        "nombre_archivo": nombre,
        "ya_cargado": dict(ya_cargado) if ya_cargado else None,
        "filas": filas,
        "duplicados_internos": duplicados_internos,
        "resumen": resumen,
        "cobertura": cobertura,
    }


def _cobertura_resultante(ctx: Contexto, filas: Sequence[dict]) -> list[dict]:
    from aplicacion.casos_uso.estado import rango_obligatorio

    hoy = date.today()
    instrumentos = {i.isin: i for i in ctx.instrumentos.listar()}
    posiciones = {p.isin: p for p in ctx.posiciones.listar()}
    por_isin: dict[str, set[str]] = {}
    for f in filas:
        if f["estado"] in (FILA_NUEVA, FILA_IDENTICA, FILA_CONFLICTO) and f.get("precio"):
            por_isin.setdefault(f["isin"], set()).add(f["fecha"])

    salida = []
    for isin, fechas_nuevas in sorted(por_isin.items()):
        instr = instrumentos.get(isin)
        pos = posiciones.get(isin)
        if instr is None or pos is None:
            salida.append({"isin": isin, "sin_posicion": True,
                           "fechas_en_archivo": len(fechas_nuevas)})
            continue
        desde, hasta = rango_obligatorio(instr, pos, hoy)
        actuales = {a_iso(x.fecha) for x in ctx.precios.por_instrumento(isin)
                    if x.precio is not None}
        cubiertas = actuales | fechas_nuevas
        requeridas = [a_iso(f) for f in rango_fechas(desde, hasta)]
        faltan = [f for f in requeridas if f not in cubiertas]
        salida.append({
            "isin": isin,
            "rango_desde": a_iso(desde),
            "rango_hasta": a_iso(hasta),
            "requeridas": len(requeridas),
            "cubiertas": len(requeridas) - len(faltan),
            "faltantes": len(faltan),
            "primeras_faltantes": faltan[:30],
            "fechas_en_archivo": len(fechas_nuevas),
        })
    return salida


def confirmar(ctx: Contexto, nombre: str, contenido: bytes, usuario: str,
              isin_forzado: str = "", permitir_periodo_cerrado: bool = False,
              justificacion: str = "") -> dict:
    """Al confirmar no se dispara recalculo: se marcan las fechas afectadas."""
    vista = previsualizar(ctx, nombre, contenido, isin_forzado)
    clave = vista["clave_idempotencia"]
    if vista["ya_cargado"]:
        # Cargar el mismo archivo dos veces no cambia nada.
        return {"idempotente": True, "carga": vista["ya_cargado"],
                "resumen": vista["resumen"], "fechas_desactualizadas": 0}

    aceptables = [f for f in vista["filas"] if f["estado"] != FILA_RECHAZADA]
    fechas = [de_iso(f["fecha"]) for f in aceptables if f["fecha"]]
    if fechas:
        cerrados = ctx.periodos.interseccion(min(fechas), max(fechas))
        if cerrados and not permitir_periodo_cerrado:
            raise PermissionError(
                "El archivo toca fechas de un periodo cerrado. Se requiere "
                "autorizacion explicita con justificacion."
            )
        if cerrados:
            for c in cerrados:
                ctx.periodos.reabrir(c["id"], usuario, justificacion or "Carga de precios")

    with ctx.bd.transaccion():
        cur = ctx.bd.ejecutar(
            "INSERT INTO carga (clave_idempotencia, nombre_archivo, momento, usuario,"
            " filas_nuevas, filas_identicas, filas_conflicto, filas_rechazadas, resumen)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (clave, nombre, ahora(), usuario, vista["resumen"]["nuevas"],
             vista["resumen"]["identicas"], vista["resumen"]["conflicto"],
             vista["resumen"]["rechazadas"],
             json.dumps(vista["resumen"], ensure_ascii=False)),
        )
        carga_id = int(cur.lastrowid)
        for f in aceptables:
            if f["estado"] == FILA_IDENTICA:
                continue
            ctx.precios.upsert(
                de_iso(f["fecha"]), f["isin"],
                dec(f["precio"]) if f["precio"] else None,
                dec(f["tipo_cambio"]) if f["tipo_cambio"] else None,
                f["fuente"], carga_id, usuario,
            )

    marcadas = 0
    por_isin: dict[str, list[date]] = {}
    for f in aceptables:
        if f["estado"] == FILA_IDENTICA:
            continue
        por_isin.setdefault(f["isin"], []).append(de_iso(f["fecha"]))
    for isin, fs in por_isin.items():
        marcadas += ctx.desactualizadas.marcar(fs, isin, "Precio cargado o corregido")

    ctx.bitacora.registrar(
        "CARGA_PRECIOS", usuario, entidad="carga", entidad_id=str(carga_id),
        detalle={"archivo": nombre, "resumen": vista["resumen"]},
        rango_desde=min(fechas) if fechas else None,
        rango_hasta=max(fechas) if fechas else None,
    )
    return {
        "idempotente": False,
        "carga_id": carga_id,
        "resumen": vista["resumen"],
        "fechas_desactualizadas": marcadas,
        "rango_desactualizado_desde": a_iso(min(fechas)) if fechas else None,
        "rango_desactualizado_hasta": a_iso(max(fechas)) if fechas else None,
        "cobertura": vista["cobertura"],
    }


def capturar_manual(ctx: Contexto, filas: Sequence[dict], usuario: str) -> dict:
    """Captura manual. Se reutiliza la misma ruta que la carga de archivo."""
    import io, csv as _csv

    buf = io.StringIO()
    w = _csv.writer(buf, lineterminator="\n")
    w.writerow(["fecha", "isin", "precio", "tipo_cambio", "fuente"])
    for f in filas:
        w.writerow([f.get("fecha", ""), f.get("isin", ""), f.get("precio", ""),
                    f.get("tipo_cambio", ""), f.get("fuente", "captura manual")])
    contenido = buf.getvalue().encode("utf-8")
    nombre = f"captura-manual-{ahora()}.csv"
    return confirmar(ctx, nombre, contenido, usuario)


def eliminar_precio(ctx: Contexto, id_precio: int, motivo: str, usuario: str) -> dict:
    if not motivo or not motivo.strip():
        raise ErrorValidacion("motivo", "El motivo de eliminacion es obligatorio.")
    r = ctx.precios.eliminar(id_precio, usuario, motivo)
    if r is None:
        raise ErrorValidacion("id", f"No existe el registro de precio {id_precio}.")
    n = ctx.desactualizadas.marcar([de_iso(r["fecha"])], r["isin"], "Precio eliminado")
    ctx.bitacora.registrar(
        "ELIMINACION_PRECIO", usuario, entidad="precio", entidad_id=str(id_precio),
        detalle={"isin": r["isin"], "fecha": r["fecha"], "motivo": motivo},
    )
    return {"eliminado": True, "isin": r["isin"], "fecha": r["fecha"],
            "fechas_desactualizadas": n}


def purgar_huerfanos(ctx: Contexto, isin: str, usuario: str, motivo: str) -> dict:
    n = ctx.precios.purgar_huerfanos(isin, usuario, motivo)
    ctx.bitacora.registrar("PURGA_PRECIOS_HUERFANOS", usuario, entidad="precio",
                           entidad_id=isin, detalle={"registros": n, "motivo": motivo})
    return {"purgados": n, "isin": isin}
