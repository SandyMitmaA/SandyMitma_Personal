"""Regresion numerica contra el archivo de referencia versionado en el repositorio."""
import json
import unittest
from pathlib import Path

from tests.generar_referencia import construir

RUTA = Path(__file__).resolve().parent / "fixtures" / "referencia.json"


class RegresionNumerica(unittest.TestCase):
    def test_la_corrida_completa_coincide_con_la_referencia(self):
        esperado = json.loads(RUTA.read_text(encoding="utf-8"))
        obtenido = construir()
        for nombre in esperado["corridas"]:
            with self.subTest(corrida=nombre):
                a = esperado["corridas"][nombre]
                b = obtenido["corridas"][nombre]
                self.assertEqual(len(a["filas"]), len(b["filas"]))
                for fa, fb in zip(a["filas"], b["filas"]):
                    self.assertEqual(fa, fb, f"{nombre} {fa['fecha']} {fa['isin']}")
                self.assertEqual(a["consolidado"], b["consolidado"])
