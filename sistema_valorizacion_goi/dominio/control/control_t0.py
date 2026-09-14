"""Columna de control a T+0. Seccion 10."""
from __future__ import annotations

from decimal import Decimal

from dominio.dinero import CERO, dec

SIN_QUIEBRE = "Sin quiebre"
UN_DIA_DE_DEVENGO = "Quiebre equivale a un dia de devengo"
REVISAR = "Revisar"

__all__ = ["clasificar_quiebre", "SIN_QUIEBRE", "UN_DIA_DE_DEVENGO", "REVISAR"]


def clasificar_quiebre(
    quiebre: Decimal, devengo_diario: Decimal, tolerancia: Decimal
) -> tuple[str, Decimal]:
    """quiebre = Total MV del control T+0 menos Total MV del sistema.

    Bajo la convencion del sistema el quiebre es, por construccion, exactamente
    un dia de devengo del portafolio con signo negativo. Devuelve el estado y
    el residual respecto de esa identidad.
    """
    residual = quiebre + devengo_diario
    if abs(quiebre) <= tolerancia:
        return SIN_QUIEBRE, residual
    if abs(residual) <= tolerancia:
        return UN_DIA_DE_DEVENGO, residual
    return REVISAR, residual
