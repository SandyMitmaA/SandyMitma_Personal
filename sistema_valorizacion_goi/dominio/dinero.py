"""Aritmetica decimal del motor. Prohibido el punto flotante binario."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from typing import Any

# Precision amplia: el motor no redondea en pasos intermedios.
getcontext().prec = 50

CERO = Decimal("0")
CIEN = Decimal("100")
UNO = Decimal("1")

__all__ = ["CERO", "CIEN", "UNO", "dec", "q", "es_decimal", "a_texto", "div"]


def dec(valor: Any) -> Decimal:
    """Convierte a Decimal. Rechaza float para que ningun binario entre al motor."""
    if valor is None or valor == "":
        return CERO
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, float):
        raise TypeError(
            "Valor float en el motor de valorizacion: "
            f"{valor!r}. Usa str o Decimal."
        )
    if isinstance(valor, bool):
        raise TypeError("Valor booleano donde se esperaba un decimal.")
    return Decimal(str(valor))


def es_decimal(valor: Any) -> bool:
    return isinstance(valor, Decimal)


def q(valor: Decimal | None, decimales: int) -> Decimal | None:
    """Cuantiza media-par. Uso exclusivo de presentacion y de reglas declaradas."""
    if valor is None:
        return None
    exp = Decimal(1).scaleb(-decimales)
    return dec(valor).quantize(exp, rounding=ROUND_HALF_EVEN)


def div(numerador: Decimal, denominador: Decimal) -> Decimal:
    if denominador == 0:
        raise ZeroDivisionError("Division por cero en el motor de valorizacion.")
    return numerador / denominador


def a_texto(valor: Decimal | None) -> str | None:
    if valor is None:
        return None
    return format(dec(valor).normalize(), "f")
