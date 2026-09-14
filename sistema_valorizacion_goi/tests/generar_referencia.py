"""Regenera el archivo de referencia numerica.

    python3 -m tests.generar_referencia

Cualquier cambio en una cifra rompe la prueba de regresion y obliga a
justificarlo antes de aceptar el nuevo archivo.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from dominio.dinero import a_texto, q
from dominio.fechas import a_iso
from dominio.valorizacion.corrida import EntradaCorrida, correr
from tests.fixtures.datos import DESDE, HASTA, INSTRUMENTOS, PARAMETROS, POSICIONES, PRECIOS

RUTA = Path(__file__).resolve().parent / "fixtures" / "referencia.json"


def construir() -> dict:
    salida: dict = {"generado_con": "convencion del sistema, desfase 1, busqueda ESTRICTA",
                    "corridas": {}}
    for nombre, caja in (("sin_caja", False), ("con_caja", True)):
        p = dataclasses.replace(PARAMETROS, incluir_caja=caja)
        r = correr(EntradaCorrida(INSTRUMENTOS, POSICIONES, PRECIOS, p), DESDE, HASTA)
        salida["corridas"][nombre] = {
            "filas": [
                {
                    "fecha": a_iso(f.fecha), "isin": f.isin,
                    "devengo_por_100": a_texto(q(f.valorizacion.devengo_por_100, 8)),
                    "security_mv_base": a_texto(q(f.valorizacion.security_mv_base, 2)),
                    "devengo_base": a_texto(q(f.valorizacion.devengo_base, 2)),
                    "total_mv_base": a_texto(q(f.valorizacion.total_mv_base, 2)),
                    "begin_mv": a_texto(q(f.puente.begin_mv, 2)),
                    "end_mv": a_texto(q(f.puente.end_mv, 2)),
                    "control": a_texto(q(f.puente.control, 6)),
                    "caja_base": a_texto(q(f.caja_base, 2)),
                    "total_mv_base_t0": a_texto(q(f.control_t0.total_mv_base, 2)),
                }
                for f in r.filas
            ],
            "consolidado": [
                {
                    "fecha": a_iso(c.fecha),
                    "total_mv_base": a_texto(q(c.total_mv_base, 2)),
                    "total_mv_base_t0": a_texto(q(c.total_mv_base_t0, 2)),
                    "caja_base": a_texto(q(c.caja_base, 2)),
                    "end_mv": a_texto(q(c.end_mv, 2)),
                    "quiebre_t0": a_texto(q(c.quiebre_t0, 2)),
                    "residual": a_texto(q(c.residual, 2)),
                    "estado_quiebre": c.estado_quiebre,
                }
                for c in r.consolidado
            ],
        }
    return salida


if __name__ == "__main__":
    RUTA.write_text(json.dumps(construir(), ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    print(f"Referencia escrita en {RUTA}")
