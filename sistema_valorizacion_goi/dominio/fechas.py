"""Aritmetica de fechas del dominio. Sin dependencias externas."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Iterator

__all__ = [
    "ultimo_dia_de_mes",
    "es_fin_de_mes",
    "restar_meses",
    "sumar_dias",
    "dias_entre",
    "dias_30360",
    "rango_fechas",
    "a_iso",
    "de_iso",
    "es_dia_habil",
]


def ultimo_dia_de_mes(anio: int, mes: int) -> int:
    return calendar.monthrange(anio, mes)[1]


def es_fin_de_mes(f: date) -> bool:
    return f.day == ultimo_dia_de_mes(f.year, f.month)


def restar_meses(f: date, meses: int) -> date:
    """Resta meses con recorte de dia al ultimo dia valido del mes destino."""
    total = (f.year * 12 + (f.month - 1)) - meses
    anio, mes = divmod(total, 12)
    mes += 1
    dia = min(f.day, ultimo_dia_de_mes(anio, mes))
    return date(anio, mes, dia)


def sumar_dias(f: date, dias: int) -> date:
    return f + timedelta(days=dias)


def dias_entre(desde: date, hasta: date) -> int:
    """Dias calendario. Positivo si hasta > desde."""
    return (hasta - desde).days


def dias_30360(desde: date, hasta: date) -> int:
    """Convencion 30/360 Bond Basis (US)."""
    d1, m1, a1 = desde.day, desde.month, desde.year
    d2, m2, a2 = hasta.day, hasta.month, hasta.year
    if d1 == 31:
        d1 = 30
    if d2 == 31 and d1 == 30:
        d2 = 30
    return 360 * (a2 - a1) + 30 * (m2 - m1) + (d2 - d1)


def rango_fechas(desde: date, hasta: date) -> Iterator[date]:
    f = desde
    while f <= hasta:
        yield f
        f = f + timedelta(days=1)


def a_iso(f: date | None) -> str | None:
    return None if f is None else f.isoformat()


def de_iso(s: str | date | None) -> date | None:
    if s is None or s == "":
        return None
    if isinstance(s, date):
        return s
    return date.fromisoformat(str(s)[:10])


def es_dia_habil(f: date) -> bool:
    """Lunes a viernes. El calendario de feriados es un parametro del despliegue."""
    return f.weekday() < 5
