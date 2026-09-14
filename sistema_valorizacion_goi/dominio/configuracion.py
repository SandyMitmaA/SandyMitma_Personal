"""Unico lugar donde viven los valores por defecto. Ningun numero magico fuera de aqui."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from dominio.dinero import dec
from dominio.fechas import de_iso, a_iso

BUSQUEDA_ESTRICTA = "ESTRICTA"
BUSQUEDA_INCLUSIVA = "INCLUSIVA"

CONVENCION_ACT_ACT = "ACT/ACT"
CONVENCION_ACT_365 = "ACT/365"
CONVENCION_ACT_360 = "ACT/360"
CONVENCION_30_360 = "30/360"
CONVENCIONES = (CONVENCION_ACT_ACT, CONVENCION_ACT_365, CONVENCION_ACT_360, CONVENCION_30_360)

PRECIO_EN_LOCAL = "LOCAL"
PRECIO_EN_BASE = "BASE"

DEFECTOS: dict[str, Any] = {
    "moneda_base": "USD",
    "fecha_inicio_portafolio": "2026-05-31",
    "desfase_devengo": "1",
    "busqueda_cupon": BUSQUEDA_ESTRICTA,
    "incluir_caja": "false",
    "valorizar_vencido_a_redencion": "false",
    "calcular_control_t0": "true",
    "dias_max_arrastre": "4",
    "tolerancia_quiebre": "0.01",
    "decimales_precio": "6",
    "decimales_tipo_cambio": "4",
    "decimales_devengo": "8",
    "decimales_monto": "2",
    # El modelo de referencia reconstruye el precio en moneda local a la
    # precision de precio declarada y usa ese valor en todo el calculo.
    # Es la unica cuantizacion que no es de presentacion y por eso es explicita.
    "cuantizar_precio_local": "true",
    "precio_local_min_razonable": "20",
    "precio_local_max_razonable": "300",
}


def _bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "t", "si", "yes", "y")


@dataclass(frozen=True)
class Parametros:
    moneda_base: str = "USD"
    fecha_inicio_portafolio: date = date(2026, 5, 31)
    desfase_devengo: int = 1
    busqueda_cupon: str = BUSQUEDA_ESTRICTA
    incluir_caja: bool = False
    valorizar_vencido_a_redencion: bool = False
    calcular_control_t0: bool = True
    dias_max_arrastre: int = 4
    tolerancia_quiebre: Decimal = Decimal("0.01")
    decimales_precio: int = 6
    decimales_tipo_cambio: int = 4
    decimales_devengo: int = 8
    decimales_monto: int = 2
    cuantizar_precio_local: bool = True
    precio_local_min_razonable: Decimal = Decimal("20")
    precio_local_max_razonable: Decimal = Decimal("300")

    @staticmethod
    def desde_mapa(mapa: Mapping[str, Any]) -> "Parametros":
        base = dict(DEFECTOS)
        base.update({k: v for k, v in mapa.items() if v is not None})
        return Parametros(
            moneda_base=str(base["moneda_base"]),
            fecha_inicio_portafolio=de_iso(base["fecha_inicio_portafolio"]),
            desfase_devengo=int(base["desfase_devengo"]),
            busqueda_cupon=str(base["busqueda_cupon"]).upper(),
            incluir_caja=_bool(base["incluir_caja"]),
            valorizar_vencido_a_redencion=_bool(base["valorizar_vencido_a_redencion"]),
            calcular_control_t0=_bool(base["calcular_control_t0"]),
            dias_max_arrastre=int(base["dias_max_arrastre"]),
            tolerancia_quiebre=dec(base["tolerancia_quiebre"]),
            decimales_precio=int(base["decimales_precio"]),
            decimales_tipo_cambio=int(base["decimales_tipo_cambio"]),
            decimales_devengo=int(base["decimales_devengo"]),
            decimales_monto=int(base["decimales_monto"]),
            cuantizar_precio_local=_bool(base["cuantizar_precio_local"]),
            precio_local_min_razonable=dec(base["precio_local_min_razonable"]),
            precio_local_max_razonable=dec(base["precio_local_max_razonable"]),
        )

    def como_control_t0(self) -> "Parametros":
        """Misma configuracion con la convencion estandar de mercado (T+0, inclusiva)."""
        from dataclasses import replace

        return replace(self, desfase_devengo=0, busqueda_cupon=BUSQUEDA_INCLUSIVA,
                       calcular_control_t0=False)

    def a_mapa(self) -> dict[str, str]:
        d = asdict(self)
        d["fecha_inicio_portafolio"] = a_iso(self.fecha_inicio_portafolio)
        return {k: ("true" if v is True else "false" if v is False else str(v))
                for k, v in d.items()}
