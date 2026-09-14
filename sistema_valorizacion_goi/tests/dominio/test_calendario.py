import unittest
from datetime import date

from dominio.valorizacion.calendario import calendario_cupones, ubicar_en_calendario


class CalendarioDeCupones(unittest.TestCase):
    def test_regla_de_fin_de_mes(self):
        # Un instrumento que vence el 30/06 paga 31/12 y 30/06, no 30/12.
        cal = calendario_cupones(date(2026, 6, 30), date(2028, 6, 30), 2)
        self.assertEqual(
            [d.isoformat() for d in cal],
            ["2026-06-30", "2026-12-31", "2027-06-30", "2027-12-31", "2028-06-30"],
        )

    def test_vencimiento_que_no_es_fin_de_mes(self):
        cal = calendario_cupones(date(2021, 4, 26), date(2031, 6, 1), 2)
        self.assertIn(date(2025, 12, 1), cal)
        self.assertIn(date(2026, 6, 1), cal)
        self.assertNotIn(date(2025, 12, 31), cal)

    def test_vencimiento_31_07(self):
        cal = calendario_cupones(date(2024, 7, 31), date(2026, 7, 31), 2)
        self.assertEqual(
            [d.isoformat() for d in cal],
            ["2024-07-31", "2025-01-31", "2025-07-31", "2026-01-31", "2026-07-31"],
        )

    def test_frecuencia_invalida(self):
        with self.assertRaises(ValueError):
            calendario_cupones(date(2020, 1, 1), date(2025, 1, 1), 0)
        with self.assertRaises(ValueError):
            calendario_cupones(date(2020, 1, 1), date(2025, 1, 1), 5)

    def test_busqueda_estricta_no_rueda_al_periodo_siguiente(self):
        cal = [date(2025, 12, 1), date(2026, 6, 1), date(2026, 12, 1)]
        ultimo, proximo = ubicar_en_calendario(cal, date(2026, 6, 1), date(2021, 4, 26), True)
        self.assertEqual(ultimo, date(2025, 12, 1))
        self.assertEqual(proximo, date(2026, 6, 1))

    def test_busqueda_inclusiva_si_rueda(self):
        cal = [date(2025, 12, 1), date(2026, 6, 1), date(2026, 12, 1)]
        ultimo, proximo = ubicar_en_calendario(cal, date(2026, 6, 1), date(2021, 4, 26), False)
        self.assertEqual(ultimo, date(2026, 6, 1))
        self.assertEqual(proximo, date(2026, 12, 1))

    def test_sin_cupon_anterior_usa_la_emision(self):
        cal = [date(2026, 6, 1)]
        ultimo, _ = ubicar_en_calendario(cal, date(2026, 1, 1), date(2025, 11, 15), True)
        self.assertEqual(ultimo, date(2025, 11, 15))

    def test_sin_proximo_cupon_devuelve_none_nunca_un_centinela(self):
        cal = [date(2026, 6, 1)]
        _, proximo = ubicar_en_calendario(cal, date(2026, 7, 1), date(2025, 1, 1), True)
        self.assertIsNone(proximo)
