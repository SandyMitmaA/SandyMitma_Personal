"""Caja. Seccion 3. El saldo se recalcula como suma de cobros, nunca se arrastra."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence

from dominio.configuracion import Parametros
from dominio.dinero import CERO, CIEN, dec
from dominio.fechas import sumar_dias
from dominio.modelos import Instrumento, Posicion
from dominio.valorizacion.motor import vigente

__all__ = ["EventoCaja", "eventos_de_caja", "saldo_origen_hasta"]


@dataclass(frozen=True)
class EventoCaja:
    fecha: date
    isin: str
    tipo: str          # CUPON | REDENCION
    monto_origen: Decimal
    moneda: str


def eventos_de_caja(
    instrumento: Instrumento,
    posicion: Posicion,
    calendario: Sequence[date],
    parametros: Parametros,
) -> list[EventoCaja]:
    """Cobros de la posicion, en la moneda de origen.

    El nominal se lee de la posicion, no de una columna de calculo que se anula
    cuando el instrumento deja de estar vigente.
    """
    nominal = dec(posicion.nominal)
    cupon_por_periodo = dec(instrumento.tasa_cupon) / dec(instrumento.frecuencia)
    monto_cupon = cupon_por_periodo / CIEN * nominal
    eventos: list[EventoCaja] = []

    for c in calendario:
        if c <= instrumento.fecha_emision or c <= posicion.fecha_alta:
            continue
        if c >= instrumento.fecha_vencimiento:
            continue
        previo = vigente(instrumento, posicion, sumar_dias(c, -1),
                         parametros.valorizar_vencido_a_redencion)
        if not previo:
            continue
        eventos.append(EventoCaja(c, instrumento.isin, "CUPON", monto_cupon, instrumento.moneda))

    venc = instrumento.fecha_vencimiento
    if posicion.fecha_alta < venc:
        redencion = nominal * (dec(1) + cupon_por_periodo / CIEN)
        eventos.append(EventoCaja(venc, instrumento.isin, "REDENCION", redencion, instrumento.moneda))

    eventos.sort(key=lambda e: (e.fecha, e.tipo))
    return eventos


def saldo_origen_hasta(eventos: Sequence[EventoCaja], f: date) -> Decimal:
    """Suma de cobros hasta la fecha. Reconstruible, no incremental."""
    total = CERO
    for e in eventos:
        if e.fecha <= f:
            total += e.monto_origen
    return total
