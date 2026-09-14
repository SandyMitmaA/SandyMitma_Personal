"""Puente Begin MV a End MV. Seccion 2.

La columna de control calcula End MV - Begin MV - suma de componentes y debe
dar cero en todas las filas. Es el mecanismo de deteccion de errores de
construccion, por eso viaja en la fila y no en los tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from dominio.dinero import CERO, CIEN, dec
from dominio.valorizacion.motor import Valorizacion

__all__ = ["ComponentesPuente", "construir_puente"]


@dataclass
class ComponentesPuente:
    begin_mv: Decimal = CERO
    efecto_precio_fx: Decimal = CERO
    devengo_dia: Decimal = CERO
    cupon_pagado: Decimal = CERO
    alta_posicion: Decimal = CERO
    baja_vencimiento: Decimal = CERO
    cobros_dia: Decimal = CERO
    efecto_fx_caja: Decimal = CERO
    end_mv: Decimal = CERO
    control: Decimal = CERO

    def suma_componentes(self) -> Decimal:
        return (
            self.efecto_precio_fx
            + self.devengo_dia
            - self.cupon_pagado
            + self.alta_posicion
            - self.baja_vencimiento
            + self.cobros_dia
            + self.efecto_fx_caja
        )


def construir_puente(
    actual: Valorizacion,
    anterior: Optional[Valorizacion],
    *,
    fecha_alta: date,
    fecha_inicio_portafolio: date,
    incluir_caja: bool,
    caja_base_actual: Decimal = CERO,
    caja_base_anterior: Decimal = CERO,
    cobros_origen_del_dia: Decimal = CERO,
    fx_actual: Decimal = dec(1),
) -> ComponentesPuente:
    c = ComponentesPuente()
    t = actual.fecha_valorizacion

    caja_t = caja_base_actual if incluir_caja else CERO
    caja_t1 = caja_base_anterior if incluir_caja else CERO

    c.end_mv = actual.total_mv_base + caja_t

    if anterior is None or t <= fecha_inicio_portafolio:
        # Foto inicial: Begin MV = End MV y la variacion es cero.
        c.begin_mv = c.end_mv
        c.control = c.end_mv - c.begin_mv - c.suma_componentes()
        return c

    c.begin_mv = anterior.total_mv_base + caja_t1

    vig_t = actual.vigente
    vig_t1 = anterior.vigente

    if vig_t and vig_t1:
        c.efecto_precio_fx = actual.security_mv_base - anterior.security_mv_base

    # Cupon pagado. Se exige vigencia tambien en t: el cupon de la fecha de
    # vencimiento viaja dentro de la redencion y contarlo aqui lo duplicaria.
    if (
        actual.es_fecha_cupon
        and vig_t
        and vig_t1
        and t > fecha_alta
        and fx_actual != 0
    ):
        c.cupon_pagado = actual.cupon_por_periodo / CIEN * actual.nominal / fx_actual

    if vig_t and vig_t1:
        c.devengo_dia = actual.devengo_base - anterior.devengo_base + c.cupon_pagado

    if vig_t and not vig_t1 and t > fecha_inicio_portafolio:
        c.alta_posicion = actual.total_mv_base

    if not vig_t and vig_t1:
        c.baja_vencimiento = anterior.total_mv_base

    if incluir_caja:
        c.cobros_dia = (cobros_origen_del_dia / fx_actual) if fx_actual != 0 else CERO
        c.efecto_fx_caja = caja_t - caja_t1 - c.cobros_dia

    c.control = c.end_mv - c.begin_mv - c.suma_componentes()
    return c
