"""Carga de ejemplo con los datos de la Parte IV, para abrir el sistema con contenido."""
from __future__ import annotations

from datetime import date

from aplicacion.casos_uso import precios as caso_precios
from aplicacion.casos_uso import registro as caso_registro
from aplicacion.casos_uso.contexto import Contexto

USUARIO = "semilla"

MAESTRA = [
    {"isin": "CA135087M276", "descripcion": "Canada 1.50% 01/06/2031", "moneda": "CAD",
     "tasa_cupon": "1.500", "frecuencia": 2, "fecha_emision": "2021-04-26",
     "fecha_vencimiento": "2031-06-01", "convencion": "ACT/ACT",
     "precio_expresado_en": "BASE", "valor_redencion": "100"},
    {"isin": "US91282CLB53", "descripcion": "US Treasury 4.375% 31/07/2026", "moneda": "USD",
     "tasa_cupon": "4.375", "frecuencia": 2, "fecha_emision": "2024-07-31",
     "fecha_vencimiento": "2026-07-31", "convencion": "ACT/ACT",
     "precio_expresado_en": "LOCAL", "valor_redencion": "100"},
    {"isin": "US91282CQY02", "descripcion": "US Treasury 4.125% 30/06/2028", "moneda": "USD",
     "tasa_cupon": "4.125", "frecuencia": 2, "fecha_emision": "2026-06-30",
     "fecha_vencimiento": "2028-06-30", "convencion": "ACT/ACT",
     "precio_expresado_en": "LOCAL", "valor_redencion": "100"},
]

POSICIONES = [
    {"isin": "CA135087M276", "nominal": "20000000", "fecha_alta": "2026-05-31"},
    {"isin": "US91282CLB53", "nominal": "50000000", "fecha_alta": "2026-05-31"},
    {"isin": "US91282CQY02", "nominal": "50000000", "fecha_alta": "2026-06-30"},
]

PRECIOS = """fecha,isin,precio,tipo_cambio,fuente
2026-05-31,CA135087M276,67.2254419008982,1.3804,proveedor
2026-06-01,CA135087M276,66.897249,1.3849,proveedor
2026-07-31,CA135087M276,65.633020,1.4028,proveedor
2026-05-31,US91282CLB53,100.105469,1,proveedor
2026-07-30,US91282CLB53,99.988281,1,proveedor
2026-06-30,US91282CQY02,99.949219,1,proveedor
2026-07-31,US91282CQY02,99.742188,1,proveedor
"""

# El juego de prueba trae precios solo en fechas sueltas y exige valorizar los
# 62 dias del periodo. Por eso el arrastre se abre a 120 dias en esta carga de
# ejemplo; el valor por defecto del sistema sigue siendo 4.
PARAMETROS = {
    "moneda_base": "USD",
    "fecha_inicio_portafolio": "2026-05-31",
    "desfase_devengo": "1",
    "busqueda_cupon": "ESTRICTA",
    "incluir_caja": "false",
    "valorizar_vencido_a_redencion": "false",
    "calcular_control_t0": "true",
    "dias_max_arrastre": "120",
    "tolerancia_quiebre": "0.01",
}


def sembrar(ctx: Contexto, con_precios: bool = True) -> dict:
    ctx.parametros.escribir(PARAMETROS, USUARIO)
    ctx.asegurar_portafolio()
    for m in MAESTRA:
        caso_registro.guardar_instrumento(ctx, m, USUARIO)
    for p in POSICIONES:
        caso_registro.guardar_posicion(ctx, p, USUARIO)
    resultado = {}
    if con_precios:
        resultado = caso_precios.confirmar(
            ctx, "precios-ejemplo.csv", PRECIOS.encode("utf-8"), USUARIO
        )
    return {"instrumentos": len(MAESTRA), "posiciones": len(POSICIONES),
            "carga": resultado}


def esta_vacia(ctx: Contexto) -> bool:
    r = ctx.bd.uno("SELECT COUNT(*) n FROM instrumento")
    return (r["n"] if r else 0) == 0
