"""Resolucion de precio y tipo de cambio por fecha. Seccion 7.1.

Todo valor arrastrado se marca como imputado. Nunca se sustituye en silencio.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from dominio.dinero import CERO, dec
from dominio.modelos import DatoMercado, Precio

__all__ = ["SeriePrecios"]


class SeriePrecios:
    """Serie de precios de un instrumento, indexada por fecha."""

    def __init__(self, precios: Iterable[Precio]) -> None:
        self._por_fecha: dict[date, Precio] = {}
        for p in precios:
            self._por_fecha[p.fecha] = p
        self._fechas: list[date] = sorted(self._por_fecha)
        self._fechas_con_precio: list[date] = [
            f for f in self._fechas if self._por_fecha[f].precio is not None
        ]
        self._fechas_con_tc: list[date] = [
            f
            for f in self._fechas
            if self._por_fecha[f].tipo_cambio not in (None, CERO)
        ]

    @property
    def fechas(self) -> list[date]:
        return list(self._fechas)

    def observado(self, f: date) -> Optional[Precio]:
        return self._por_fecha.get(f)

    def _ultima_hasta(self, fechas: list[date], f: date, inclusive: bool) -> Optional[date]:
        i = bisect_right(fechas, f) if inclusive else bisect_left(fechas, f)
        return fechas[i - 1] if i > 0 else None

    def tipo_cambio_vigente(self, f: date) -> tuple[Optional[Decimal], Optional[date], bool]:
        """Ultimo tipo de cambio habil disponible. Arrastre sin limite de dias."""
        exacto = self._por_fecha.get(f)
        if exacto is not None and exacto.tipo_cambio not in (None, CERO):
            return dec(exacto.tipo_cambio), f, False
        origen = self._ultima_hasta(self._fechas_con_tc, f, inclusive=True)
        if origen is None:
            return None, None, False
        return dec(self._por_fecha[origen].tipo_cambio), origen, True

    def resolver(self, f: date, dias_max_arrastre: int) -> DatoMercado:
        tc, origen_tc, tc_imputado = self.tipo_cambio_vigente(f)

        exacto = self._por_fecha.get(f)
        if exacto is not None and exacto.precio is not None:
            return DatoMercado(
                precio=dec(exacto.precio),
                tipo_cambio=tc,
                precio_imputado=False,
                tipo_cambio_imputado=tc_imputado,
                fecha_origen_precio=f,
                fecha_origen_tipo_cambio=origen_tc,
                dias_arrastre_precio=0,
                error="" if tc not in (None, CERO) else "Tipo de cambio ausente o en cero.",
            )

        origen = self._ultima_hasta(self._fechas_con_precio, f, inclusive=False)
        if origen is None:
            return DatoMercado(
                precio=None,
                tipo_cambio=tc,
                tipo_cambio_imputado=tc_imputado,
                fecha_origen_tipo_cambio=origen_tc,
                error="Sin precio previo disponible para arrastre.",
            )
        dias = (f - origen).days
        if dias > max(dias_max_arrastre, 0):
            return DatoMercado(
                precio=None,
                tipo_cambio=tc,
                tipo_cambio_imputado=tc_imputado,
                fecha_origen_precio=origen,
                fecha_origen_tipo_cambio=origen_tc,
                dias_arrastre_precio=dias,
                error=(
                    f"Sin precio: el ultimo disponible es del {origen.isoformat()}, "
                    f"{dias} dias atras, sobre el limite de arrastre de {dias_max_arrastre}."
                ),
            )
        return DatoMercado(
            precio=dec(self._por_fecha[origen].precio),
            tipo_cambio=tc,
            precio_imputado=True,
            tipo_cambio_imputado=tc_imputado,
            fecha_origen_precio=origen,
            fecha_origen_tipo_cambio=origen_tc,
            dias_arrastre_precio=dias,
            error="" if tc not in (None, CERO) else "Tipo de cambio ausente o en cero.",
        )
