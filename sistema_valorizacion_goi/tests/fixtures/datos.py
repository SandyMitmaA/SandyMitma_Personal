"""Datos de la Parte IV. Fixtures compartidos por todas las capas de prueba."""
from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal as D

from dominio.configuracion import Parametros
from dominio.modelos import Instrumento, Posicion, Precio

# El juego de prueba trae precios en fechas sueltas y exige valorizar los 62
# dias del periodo, asi que el arrastre se abre. El defecto del sistema es 4.
PARAMETROS = dataclasses.replace(Parametros(), dias_max_arrastre=120)

CA = Instrumento("CA135087M276", "CAD", D("1.500"), 2, date(2021, 4, 26),
                 date(2031, 6, 1), "ACT/ACT", "BASE", D("100"))
LB = Instrumento("US91282CLB53", "USD", D("4.375"), 2, date(2024, 7, 31),
                 date(2026, 7, 31), "ACT/ACT", "LOCAL", D("100"))
QY = Instrumento("US91282CQY02", "USD", D("4.125"), 2, date(2026, 6, 30),
                 date(2028, 6, 30), "ACT/ACT", "LOCAL", D("100"))

INSTRUMENTOS = {i.isin: i for i in (CA, LB, QY)}

POS_CA = Posicion(1, CA.isin, D("20000000"), date(2026, 5, 31))
POS_LB = Posicion(2, LB.isin, D("50000000"), date(2026, 5, 31))
POS_QY = Posicion(3, QY.isin, D("50000000"), date(2026, 6, 30))
POSICIONES = [POS_CA, POS_LB, POS_QY]

PRECIOS = {
    CA.isin: [
        Precio(date(2026, 5, 31), CA.isin, D("67.2254419008982"), D("1.3804")),
        Precio(date(2026, 6, 1), CA.isin, D("66.897249"), D("1.3849")),
        Precio(date(2026, 7, 31), CA.isin, D("65.633020"), D("1.4028")),
    ],
    LB.isin: [
        Precio(date(2026, 5, 31), LB.isin, D("100.105469"), D("1")),
        Precio(date(2026, 7, 30), LB.isin, D("99.988281"), D("1")),
    ],
    QY.isin: [
        Precio(date(2026, 6, 30), QY.isin, D("99.949219"), D("1")),
        Precio(date(2026, 7, 31), QY.isin, D("99.742188"), D("1")),
    ],
}

DESDE = date(2026, 5, 31)
HASTA = date(2026, 7, 31)

# Tolerancia declarada. Prohibido comparar montos con igualdad exacta.
TOLERANCIA = D("0.005")
TOLERANCIA_CONTROL = D("0.0000001")
