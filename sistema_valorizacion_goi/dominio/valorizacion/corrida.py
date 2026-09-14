"""Corrida de valorizacion de un rango. Servicio de dominio puro.

El motor no acumula estado: cada fecha se calcula desde la maestra, las
posiciones y los precios vigentes, mas el End MV del dia anterior, que a su vez
es recalculable por la misma regla. Reejecutar produce el mismo resultado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional, Sequence

from dominio.caja.caja import EventoCaja, eventos_de_caja, saldo_origen_hasta
from dominio.configuracion import Parametros
from dominio.control.control_t0 import clasificar_quiebre
from dominio.dinero import CERO, dec, q
from dominio.fechas import a_iso, rango_fechas, sumar_dias
from dominio.modelos import Instrumento, Posicion, Precio
from dominio.puente.puente import ComponentesPuente, construir_puente
from dominio.valorizacion.calendario import calendario_cupones
from dominio.valorizacion.motor import (
    Valorizacion,
    devengo_diario_teorico,
    valorizar,
    vigente,
)
from dominio.valorizacion.series import SeriePrecios

__all__ = ["Fila", "FilaConsolidada", "ResultadoCorrida", "EntradaCorrida", "correr"]


@dataclass
class Fila:
    valorizacion: Valorizacion
    control_t0: Optional[Valorizacion]
    puente: ComponentesPuente
    caja_origen: Decimal
    caja_base: Decimal
    cobros_origen_dia: Decimal
    devengo_diario: Decimal
    quiebre_t0: Decimal

    @property
    def fecha(self) -> date:
        return self.valorizacion.fecha_valorizacion

    @property
    def isin(self) -> str:
        return self.valorizacion.isin


@dataclass
class FilaConsolidada:
    fecha: date
    total_mv_base: Decimal
    total_mv_base_t0: Decimal
    caja_base: Decimal
    begin_mv: Decimal
    end_mv: Decimal
    efecto_precio_fx: Decimal
    devengo_dia: Decimal
    cupon_pagado: Decimal
    alta_posicion: Decimal
    baja_vencimiento: Decimal
    cobros_dia: Decimal
    efecto_fx_caja: Decimal
    control: Decimal
    quiebre_t0: Decimal
    devengo_diario: Decimal
    residual: Decimal
    estado_quiebre: str


@dataclass
class EntradaCorrida:
    """Todo lo que el motor necesita. No hay ninguna otra fuente de datos."""
    instrumentos: dict[str, Instrumento]
    posiciones: Sequence[Posicion]
    precios: dict[str, Sequence[Precio]]
    parametros: Parametros


@dataclass
class ResultadoCorrida:
    filas: list[Fila] = field(default_factory=list)
    consolidado: list[FilaConsolidada] = field(default_factory=list)
    calendarios: dict[str, list[date]] = field(default_factory=dict)


def correr(entrada: EntradaCorrida, desde: date, hasta: date) -> ResultadoCorrida:
    p = entrada.parametros
    resultado = ResultadoCorrida()

    # Fecha de calentamiento: el dia anterior al rango, necesario para el
    # puente. Es recalculable desde los mismos datos, no es estado arrastrado.
    inicio_calculo = max(sumar_dias(desde, -1), p.fecha_inicio_portafolio)
    if desde <= p.fecha_inicio_portafolio:
        inicio_calculo = desde

    por_fecha: dict[date, list[Fila]] = {}

    for pos in entrada.posiciones:
        instr = entrada.instrumentos.get(pos.isin)
        if instr is None:
            continue
        cal = calendario_cupones(instr.fecha_emision, instr.fecha_vencimiento, instr.frecuencia)
        resultado.calendarios[instr.isin] = cal
        serie = SeriePrecios(entrada.precios.get(pos.isin, []))
        eventos = eventos_de_caja(instr, pos, cal, p)

        anterior: Optional[Valorizacion] = None
        caja_base_anterior = CERO

        for f in rango_fechas(inicio_calculo, hasta):
            mercado = serie.resolver(f, p.dias_max_arrastre)
            v = valorizar(instr, pos, f, mercado, p, cal)

            v_t0: Optional[Valorizacion] = None
            if p.calcular_control_t0:
                v_t0 = valorizar(instr, pos, f, mercado, p.como_control_t0(), cal)

            # Caja en moneda de origen y su reexpresion a base.
            caja_origen = saldo_origen_hasta(eventos, f)
            cobros_dia = sum(
                (e.monto_origen for e in eventos if e.fecha == f), CERO
            )
            if instr.moneda == p.moneda_base:
                fx_caja = dec(1)
            else:
                tc, _, _ = serie.tipo_cambio_vigente(f)
                fx_caja = dec(tc) if tc not in (None, CERO) else CERO
            caja_base = (caja_origen / fx_caja) if fx_caja != 0 else CERO

            puente = construir_puente(
                v,
                anterior,
                fecha_alta=pos.fecha_alta,
                fecha_inicio_portafolio=p.fecha_inicio_portafolio,
                incluir_caja=p.incluir_caja,
                caja_base_actual=caja_base,
                caja_base_anterior=caja_base_anterior,
                cobros_origen_del_dia=cobros_dia,
                fx_actual=fx_caja if fx_caja != 0 else dec(1),
            )

            quiebre = (v_t0.total_mv_base - v.total_mv_base) if v_t0 else CERO
            fila = Fila(
                valorizacion=v,
                control_t0=v_t0,
                puente=puente,
                caja_origen=caja_origen,
                caja_base=caja_base,
                cobros_origen_dia=cobros_dia,
                devengo_diario=devengo_diario_teorico(v),
                quiebre_t0=quiebre,
            )
            if f >= desde:
                por_fecha.setdefault(f, []).append(fila)
                resultado.filas.append(fila)

            anterior = v
            caja_base_anterior = caja_base

    for f in rango_fechas(desde, hasta):
        filas = por_fecha.get(f, [])
        cons = FilaConsolidada(
            fecha=f,
            total_mv_base=sum((x.valorizacion.total_mv_base for x in filas), CERO),
            total_mv_base_t0=sum(
                (x.control_t0.total_mv_base for x in filas if x.control_t0), CERO
            ),
            caja_base=sum((x.caja_base for x in filas), CERO) if p.incluir_caja else CERO,
            begin_mv=sum((x.puente.begin_mv for x in filas), CERO),
            end_mv=sum((x.puente.end_mv for x in filas), CERO),
            efecto_precio_fx=sum((x.puente.efecto_precio_fx for x in filas), CERO),
            devengo_dia=sum((x.puente.devengo_dia for x in filas), CERO),
            cupon_pagado=sum((x.puente.cupon_pagado for x in filas), CERO),
            alta_posicion=sum((x.puente.alta_posicion for x in filas), CERO),
            baja_vencimiento=sum((x.puente.baja_vencimiento for x in filas), CERO),
            cobros_dia=sum((x.puente.cobros_dia for x in filas), CERO),
            efecto_fx_caja=sum((x.puente.efecto_fx_caja for x in filas), CERO),
            control=sum((x.puente.control for x in filas), CERO),
            quiebre_t0=sum((x.quiebre_t0 for x in filas), CERO),
            devengo_diario=sum((x.devengo_diario for x in filas), CERO),
            residual=CERO,
            estado_quiebre="",
        )
        estado, residual = clasificar_quiebre(
            cons.quiebre_t0, cons.devengo_diario, p.tolerancia_quiebre
        )
        cons.estado_quiebre = estado
        cons.residual = residual
        resultado.consolidado.append(cons)

    resultado.filas.sort(key=lambda x: (x.fecha, x.isin))
    return resultado
