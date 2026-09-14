"""Entidades del dominio. Estructuras de datos puras, sin persistencia."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from dominio.configuracion import PRECIO_EN_LOCAL

ESTADO_REGISTRADO = "Registrado"
ESTADO_SIN_PRECIOS = "Sin precios"
ESTADO_COBERTURA_PARCIAL = "Cobertura parcial"
ESTADO_LISTO = "Listo"
ESTADO_VALORIZADO = "Valorizado"

EVENTO_NINGUNO = ""
EVENTO_CUPON = "CUPON"
EVENTO_VENCIMIENTO = "VENCIMIENTO"
EVENTO_ALTA = "ALTA"
EVENTO_REDENCION = "REDENCION"


@dataclass(frozen=True)
class Instrumento:
    isin: str
    moneda: str
    tasa_cupon: Decimal
    frecuencia: int
    fecha_emision: date
    fecha_vencimiento: date
    convencion: str
    precio_expresado_en: str = PRECIO_EN_LOCAL
    valor_redencion: Decimal = Decimal("100")
    descripcion: str = ""
    eliminado_en: Optional[str] = None


@dataclass(frozen=True)
class Posicion:
    id: int
    isin: str
    nominal: Decimal
    fecha_alta: date
    eliminado_en: Optional[str] = None


@dataclass(frozen=True)
class Precio:
    fecha: date
    isin: str
    precio: Decimal
    tipo_cambio: Optional[Decimal]
    fuente: str = ""


@dataclass(frozen=True)
class DatoMercado:
    """Precio y tipo de cambio efectivamente usados, con su trazabilidad."""
    precio: Optional[Decimal]
    tipo_cambio: Optional[Decimal]
    precio_imputado: bool = False
    tipo_cambio_imputado: bool = False
    fecha_origen_precio: Optional[date] = None
    fecha_origen_tipo_cambio: Optional[date] = None
    dias_arrastre_precio: int = 0
    error: str = ""
