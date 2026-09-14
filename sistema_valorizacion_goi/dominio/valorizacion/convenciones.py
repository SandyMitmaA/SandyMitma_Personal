"""Convenciones de conteo de dias. Se toman de la maestra y no se alteran."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from dominio.configuracion import (
    CONVENCION_30_360,
    CONVENCION_ACT_360,
    CONVENCION_ACT_365,
    CONVENCION_ACT_ACT,
)
from dominio.dinero import CERO, dec, div
from dominio.fechas import dias_30360

__all__ = ["devengo_por_100", "convencion_de_mercado_sugerida"]


def devengo_por_100(
    convencion: str,
    tasa_cupon: Decimal,
    cupon_por_periodo: Decimal,
    frecuencia: int,
    ultimo_cupon: date,
    fecha_devengo: date,
    dias_transcurridos: int,
    dias_periodo: int,
) -> Decimal:
    """Seccion 1.4. Devengo expresado por cada 100 de nominal."""
    conv = (convencion or "").upper().strip()
    if conv == CONVENCION_ACT_ACT:
        if dias_periodo == 0:
            return CERO
        return cupon_por_periodo * dec(dias_transcurridos) / dec(dias_periodo)
    if conv == CONVENCION_ACT_365:
        return tasa_cupon * dec(dias_transcurridos) / dec(365)
    if conv == CONVENCION_ACT_360:
        return tasa_cupon * dec(dias_transcurridos) / dec(360)
    if conv == CONVENCION_30_360:
        d30 = dias_30360(ultimo_cupon, fecha_devengo)
        base = dec(360) / dec(frecuencia)
        if base == 0:
            return CERO
        return cupon_por_periodo * dec(d30) / base
    raise ValueError(f"Convencion de dias no soportada: {convencion!r}")


# Uso de mercado por moneda y tipo de emisor. Solo informativo: alimenta el
# panel de validaciones con impacto cuantificado. El motor jamas lo aplica.
USO_DE_MERCADO: dict[str, str] = {
    "CAD": CONVENCION_ACT_365,
    "USD": CONVENCION_ACT_ACT,
    "GBP": CONVENCION_ACT_ACT,
    "EUR": CONVENCION_ACT_ACT,
    "AUD": CONVENCION_ACT_ACT,
    "JPY": CONVENCION_ACT_365,
    "PEN": CONVENCION_ACT_360,
}


def convencion_de_mercado_sugerida(moneda: str) -> str | None:
    return USO_DE_MERCADO.get((moneda or "").upper())
