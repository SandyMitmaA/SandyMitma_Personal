"""Calendario de cupones. Se deriva del vencimiento y la frecuencia. Nunca se captura."""
from __future__ import annotations

from datetime import date
from typing import Sequence

from dominio.fechas import es_fin_de_mes, restar_meses, ultimo_dia_de_mes

__all__ = ["calendario_cupones", "ubicar_en_calendario"]


def calendario_cupones(
    fecha_emision: date, fecha_vencimiento: date, frecuencia: int
) -> list[date]:
    """Seccion 1.1. Retrocede desde el vencimiento con regla de fin de mes.

    El bucle agrega la fecha calculada antes de reevaluar la condicion, por lo
    que la primera fecha del calendario puede ser anterior a la emision. Es el
    comportamiento especificado y se implementa literalmente.
    """
    if frecuencia <= 0:
        raise ValueError("La frecuencia de cupon debe ser mayor que cero.")
    if 12 % frecuencia != 0:
        raise ValueError("La frecuencia debe dividir exactamente a 12.")

    paso = 12 // frecuencia
    fin_de_mes = es_fin_de_mes(fecha_vencimiento)
    fechas: list[date] = [fecha_vencimiento]
    d = fecha_vencimiento
    guarda = 0
    while d > fecha_emision:
        guarda += 1
        if guarda > 4000:
            raise RuntimeError("Calendario de cupones sin convergencia.")
        d = restar_meses(d, paso)
        if fin_de_mes:
            d = date(d.year, d.month, ultimo_dia_de_mes(d.year, d.month))
        fechas.append(d)
    fechas.sort()
    return fechas


def ubicar_en_calendario(
    fechas: Sequence[date],
    fecha_devengo: date,
    fecha_emision: date,
    estricta: bool,
) -> tuple[date, date | None]:
    """Seccion 1.2. Los operadores son el nucleo de la metodologia.

    ESTRICTA : ultimo  = max(f < fecha_devengo) ; proximo = min(f >= fecha_devengo)
    INCLUSIVA: ultimo  = max(f <= fecha_devengo); proximo = min(f >  fecha_devengo)

    Devuelve (ultimo_cupon, proximo_cupon). proximo_cupon es None cuando no
    existe: quien llame debe haber aplicado antes la guarda de vencimiento.
    Nunca se sustituye por una fecha centinela.
    """
    if estricta:
        anteriores = [f for f in fechas if f < fecha_devengo]
        posteriores = [f for f in fechas if f >= fecha_devengo]
    else:
        anteriores = [f for f in fechas if f <= fecha_devengo]
        posteriores = [f for f in fechas if f > fecha_devengo]

    ultimo = max(anteriores) if anteriores else fecha_emision
    proximo = min(posteriores) if posteriores else None
    return ultimo, proximo
