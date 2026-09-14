"""Motor de valorizacion. Libreria pura: recibe datos y devuelve resultados.

No conoce base de datos, HTTP ni framework. Se puede ejecutar en un test
unitario cargando una maestra, una posicion y un precio en memoria.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional, Sequence

from dominio.configuracion import (
    BUSQUEDA_ESTRICTA,
    PRECIO_EN_BASE,
    Parametros,
)
from dominio.dinero import CERO, CIEN, dec, q
from dominio.fechas import sumar_dias
from dominio.modelos import (
    EVENTO_CUPON,
    EVENTO_NINGUNO,
    EVENTO_VENCIMIENTO,
    DatoMercado,
    Instrumento,
    Posicion,
)
from dominio.valorizacion.calendario import calendario_cupones, ubicar_en_calendario
from dominio.valorizacion.convenciones import devengo_por_100

__all__ = ["Valorizacion", "vigente", "valorizar", "devengo_diario_teorico"]


@dataclass
class Valorizacion:
    """Una fila de la grilla. Expone todos los campos intermedios."""

    fecha_valorizacion: date
    isin: str
    posicion_id: int
    nominal: Decimal
    vigente: bool

    fecha_devengo: date
    ultimo_cupon: Optional[date]
    proximo_cupon: Optional[date]
    dias_transcurridos: int
    dias_periodo: int
    cupon_por_periodo: Decimal
    devengo_por_100: Decimal

    precio_proveedor: Optional[Decimal]
    precio_local: Optional[Decimal]
    tipo_cambio: Optional[Decimal]
    precio_imputado: bool
    tipo_cambio_imputado: bool
    dias_arrastre_precio: int
    fecha_origen_precio: Optional[date]
    fecha_origen_tipo_cambio: Optional[date]

    security_mv_local: Decimal
    devengo_local: Decimal
    total_mv_local: Decimal
    fx: Decimal
    security_mv_base: Decimal
    devengo_base: Decimal
    total_mv_base: Decimal

    evento: str = EVENTO_NINGUNO
    es_fecha_cupon: bool = False
    a_redencion: bool = False
    error: str = ""

    def como_dict(self) -> dict:
        from dominio.dinero import a_texto
        from dominio.fechas import a_iso

        return {
            "fecha_valorizacion": a_iso(self.fecha_valorizacion),
            "isin": self.isin,
            "posicion_id": self.posicion_id,
            "nominal": a_texto(self.nominal),
            "vigente": self.vigente,
            "fecha_devengo": a_iso(self.fecha_devengo),
            "ultimo_cupon": a_iso(self.ultimo_cupon),
            "proximo_cupon": a_iso(self.proximo_cupon),
            "dias_transcurridos": self.dias_transcurridos,
            "dias_periodo": self.dias_periodo,
            "cupon_por_periodo": a_texto(self.cupon_por_periodo),
            "devengo_por_100": a_texto(self.devengo_por_100),
            "precio_proveedor": a_texto(self.precio_proveedor),
            "precio_local": a_texto(self.precio_local),
            "tipo_cambio": a_texto(self.tipo_cambio),
            "precio_imputado": self.precio_imputado,
            "tipo_cambio_imputado": self.tipo_cambio_imputado,
            "dias_arrastre_precio": self.dias_arrastre_precio,
            "fecha_origen_precio": a_iso(self.fecha_origen_precio),
            "fecha_origen_tipo_cambio": a_iso(self.fecha_origen_tipo_cambio),
            "security_mv_local": a_texto(self.security_mv_local),
            "devengo_local": a_texto(self.devengo_local),
            "total_mv_local": a_texto(self.total_mv_local),
            "fx": a_texto(self.fx),
            "security_mv_base": a_texto(self.security_mv_base),
            "devengo_base": a_texto(self.devengo_base),
            "total_mv_base": a_texto(self.total_mv_base),
            "evento": self.evento,
            "es_fecha_cupon": self.es_fecha_cupon,
            "a_redencion": self.a_redencion,
            "error": self.error,
        }


def vigente(
    instrumento: Instrumento,
    posicion: Posicion,
    fecha: date,
    valorizar_vencido_a_redencion: bool,
) -> bool:
    """Seccion 1.5. El instrumento sale de la cartera el dia de su vencimiento."""
    if fecha < posicion.fecha_alta:
        return False
    if valorizar_vencido_a_redencion:
        return fecha <= instrumento.fecha_vencimiento
    return fecha < instrumento.fecha_vencimiento


def _precio_local(
    instrumento: Instrumento,
    precio_proveedor: Decimal,
    tipo_cambio: Decimal,
    parametros: Parametros,
) -> Decimal:
    """Seccion 1.6. Reconstruye el precio en la moneda del instrumento."""
    if instrumento.precio_expresado_en == PRECIO_EN_BASE:
        bruto = precio_proveedor * tipo_cambio
    else:
        bruto = precio_proveedor
    if parametros.cuantizar_precio_local:
        return q(bruto, parametros.decimales_precio)
    return bruto


def valorizar(
    instrumento: Instrumento,
    posicion: Posicion,
    fecha_valorizacion: date,
    mercado: DatoMercado,
    parametros: Parametros,
    calendario: Sequence[date] | None = None,
) -> Valorizacion:
    """Valoriza una posicion en una fecha. Punto de entrada del motor."""
    cal = list(calendario) if calendario is not None else calendario_cupones(
        instrumento.fecha_emision, instrumento.fecha_vencimiento, instrumento.frecuencia
    )

    fecha_devengo = sumar_dias(fecha_valorizacion, parametros.desfase_devengo)
    estricta = parametros.busqueda_cupon == BUSQUEDA_ESTRICTA
    cupon_por_periodo = dec(instrumento.tasa_cupon) / dec(instrumento.frecuencia)

    esta_vigente = vigente(
        instrumento, posicion, fecha_valorizacion, parametros.valorizar_vencido_a_redencion
    )
    es_dia_de_vencimiento = fecha_valorizacion == instrumento.fecha_vencimiento
    a_redencion = (
        parametros.valorizar_vencido_a_redencion
        and es_dia_de_vencimiento
        and esta_vigente
    )

    # --- Devengo -----------------------------------------------------------
    ultimo_cupon: Optional[date] = None
    proximo_cupon: Optional[date] = None
    if fecha_devengo <= instrumento.fecha_vencimiento:
        ultimo_cupon, proximo_cupon = ubicar_en_calendario(
            cal, fecha_devengo, instrumento.fecha_emision, estricta
        )

    if fecha_devengo > instrumento.fecha_vencimiento or proximo_cupon is None:
        # Seccion 1.3. Guarda de vencimiento. Operador mayor estricto: con
        # fecha_devengo igual al vencimiento la guarda no dispara bajo busqueda
        # estricta y el devengo sale por la via normal, dando el periodo
        # completo. Bajo busqueda inclusiva -la convencion del control T+0- esa
        # misma fecha deja el calendario sin proximo cupon, y entonces si
        # aplica: no hay periodo al que devengar. Nunca se usa una fecha de
        # relleno para completar el calendario.
        ultimo_cupon = instrumento.fecha_vencimiento
        proximo_cupon = instrumento.fecha_vencimiento
        dias_transcurridos = 0
        dias_periodo = 0
        devengo_100 = CERO
    else:
        dias_transcurridos = (fecha_devengo - ultimo_cupon).days
        dias_periodo = (proximo_cupon - ultimo_cupon).days
        devengo_100 = devengo_por_100(
            instrumento.convencion,
            dec(instrumento.tasa_cupon),
            cupon_por_periodo,
            instrumento.frecuencia,
            ultimo_cupon,
            fecha_devengo,
            dias_transcurridos,
            dias_periodo,
        )

    if a_redencion:
        # El dia de vencimiento se valoriza a redencion con cupon completo,
        # ignorando cualquier precio de mercado.
        devengo_100 = cupon_por_periodo

    nominal = dec(posicion.nominal)
    es_fecha_cupon = fecha_valorizacion in cal and fecha_valorizacion > instrumento.fecha_emision

    if not esta_vigente:
        return Valorizacion(
            fecha_valorizacion=fecha_valorizacion,
            isin=instrumento.isin,
            posicion_id=posicion.id,
            nominal=nominal,
            vigente=False,
            fecha_devengo=fecha_devengo,
            ultimo_cupon=ultimo_cupon,
            proximo_cupon=proximo_cupon,
            dias_transcurridos=dias_transcurridos,
            dias_periodo=dias_periodo,
            cupon_por_periodo=cupon_por_periodo,
            devengo_por_100=CERO,
            precio_proveedor=mercado.precio,
            precio_local=None,
            tipo_cambio=mercado.tipo_cambio,
            precio_imputado=False,
            tipo_cambio_imputado=False,
            dias_arrastre_precio=0,
            fecha_origen_precio=None,
            fecha_origen_tipo_cambio=None,
            security_mv_local=CERO,
            devengo_local=CERO,
            total_mv_local=CERO,
            fx=dec(1),
            security_mv_base=CERO,
            devengo_base=CERO,
            total_mv_base=CERO,
            evento=EVENTO_VENCIMIENTO if es_dia_de_vencimiento else EVENTO_NINGUNO,
            es_fecha_cupon=es_fecha_cupon,
            a_redencion=False,
            error="",
        )

    # --- Precio, tipo de cambio y valor de mercado -------------------------
    tipo_cambio = mercado.tipo_cambio
    if instrumento.moneda == parametros.moneda_base:
        tipo_cambio = dec(1) if tipo_cambio in (None, CERO) else tipo_cambio
    error = mercado.error
    if tipo_cambio is None or tipo_cambio == 0:
        error = error or "Tipo de cambio ausente o en cero."

    if a_redencion:
        precio_proveedor = dec(instrumento.valor_redencion)
        precio_local_v = dec(instrumento.valor_redencion)
    else:
        precio_proveedor = mercado.precio
        precio_local_v = (
            _precio_local(instrumento, precio_proveedor, tipo_cambio, parametros)
            if precio_proveedor is not None and tipo_cambio not in (None, CERO)
            else None
        )

    if precio_proveedor is None:
        error = error or "Sin precio para una fecha vigente."

    if error or precio_local_v is None or tipo_cambio in (None, CERO):
        return Valorizacion(
            fecha_valorizacion=fecha_valorizacion,
            isin=instrumento.isin,
            posicion_id=posicion.id,
            nominal=nominal,
            vigente=True,
            fecha_devengo=fecha_devengo,
            ultimo_cupon=ultimo_cupon,
            proximo_cupon=proximo_cupon,
            dias_transcurridos=dias_transcurridos,
            dias_periodo=dias_periodo,
            cupon_por_periodo=cupon_por_periodo,
            devengo_por_100=devengo_100,
            precio_proveedor=precio_proveedor,
            precio_local=precio_local_v,
            tipo_cambio=tipo_cambio,
            precio_imputado=mercado.precio_imputado,
            tipo_cambio_imputado=mercado.tipo_cambio_imputado,
            dias_arrastre_precio=mercado.dias_arrastre_precio,
            fecha_origen_precio=mercado.fecha_origen_precio,
            fecha_origen_tipo_cambio=mercado.fecha_origen_tipo_cambio,
            security_mv_local=CERO,
            devengo_local=CERO,
            total_mv_local=CERO,
            fx=dec(1),
            security_mv_base=CERO,
            devengo_base=CERO,
            total_mv_base=CERO,
            evento=EVENTO_CUPON if es_fecha_cupon else EVENTO_NINGUNO,
            es_fecha_cupon=es_fecha_cupon,
            a_redencion=a_redencion,
            error=error or "Sin precio utilizable.",
        )

    # Seccion 1.7
    security_mv_local = precio_local_v / CIEN * nominal
    devengo_local = devengo_100 / CIEN * nominal
    total_mv_local = security_mv_local + devengo_local

    fx = dec(1) if instrumento.moneda == parametros.moneda_base else dec(tipo_cambio)
    security_mv_base = security_mv_local / fx
    devengo_base = devengo_local / fx
    total_mv_base = security_mv_base + devengo_base

    evento = EVENTO_NINGUNO
    if a_redencion:
        evento = EVENTO_VENCIMIENTO
    elif es_fecha_cupon:
        evento = EVENTO_CUPON

    return Valorizacion(
        fecha_valorizacion=fecha_valorizacion,
        isin=instrumento.isin,
        posicion_id=posicion.id,
        nominal=nominal,
        vigente=True,
        fecha_devengo=fecha_devengo,
        ultimo_cupon=ultimo_cupon,
        proximo_cupon=proximo_cupon,
        dias_transcurridos=dias_transcurridos,
        dias_periodo=dias_periodo,
        cupon_por_periodo=cupon_por_periodo,
        devengo_por_100=devengo_100,
        precio_proveedor=precio_proveedor,
        precio_local=precio_local_v,
        tipo_cambio=dec(tipo_cambio),
        precio_imputado=mercado.precio_imputado,
        tipo_cambio_imputado=mercado.tipo_cambio_imputado,
        dias_arrastre_precio=mercado.dias_arrastre_precio,
        fecha_origen_precio=mercado.fecha_origen_precio,
        fecha_origen_tipo_cambio=mercado.fecha_origen_tipo_cambio,
        security_mv_local=security_mv_local,
        devengo_local=devengo_local,
        total_mv_local=total_mv_local,
        fx=fx,
        security_mv_base=security_mv_base,
        devengo_base=devengo_base,
        total_mv_base=total_mv_base,
        evento=evento,
        es_fecha_cupon=es_fecha_cupon,
        a_redencion=a_redencion,
        error="",
    )


def devengo_diario_teorico(v: Valorizacion) -> Decimal:
    """Seccion 10. cupon_por_periodo / 100 * nominal / dias_periodo, en base."""
    if not v.vigente or v.dias_periodo == 0 or v.fx == 0:
        return CERO
    return v.cupon_por_periodo / CIEN * v.nominal / dec(v.dias_periodo) / v.fx
