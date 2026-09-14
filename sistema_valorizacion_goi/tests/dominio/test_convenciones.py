import unittest
from datetime import date
from decimal import Decimal as D

from dominio.dinero import q
from dominio.valorizacion.convenciones import devengo_por_100


class Convenciones(unittest.TestCase):
    def test_act_act(self):
        r = devengo_por_100("ACT/ACT", D("4.375"), D("2.1875"), 2,
                            date(2026, 1, 31), date(2026, 6, 1), 121, 181)
        self.assertEqual(q(r, 8), D("1.46236188"))

    def test_act_365(self):
        r = devengo_por_100("ACT/365", D("1.5"), D("0.75"), 2,
                            date(2025, 12, 1), date(2026, 6, 1), 182, 182)
        self.assertEqual(q(r, 8), q(D("1.5") * 182 / 365, 8))

    def test_act_360(self):
        r = devengo_por_100("ACT/360", D("1.5"), D("0.75"), 2,
                            date(2025, 12, 1), date(2026, 6, 1), 182, 182)
        self.assertEqual(q(r, 8), q(D("1.5") * 182 / 360, 8))

    def test_30_360(self):
        # 01/12/2025 a 01/06/2026 son 180 dias 30/360; medio periodo semestral.
        r = devengo_por_100("30/360", D("1.5"), D("0.75"), 2,
                            date(2025, 12, 1), date(2026, 6, 1), 182, 182)
        self.assertEqual(q(r, 8), D("0.75000000"))

    def test_30_360_recorta_el_dia_31(self):
        r = devengo_por_100("30/360", D("4.0"), D("2.0"), 2,
                            date(2026, 1, 31), date(2026, 7, 31), 181, 181)
        self.assertEqual(q(r, 8), D("2.00000000"))

    def test_periodo_cero_no_divide_por_cero(self):
        self.assertEqual(devengo_por_100("ACT/ACT", D("4"), D("2"), 2,
                                         date(2026, 1, 1), date(2026, 1, 1), 0, 0), 0)

    def test_convencion_desconocida(self):
        with self.assertRaises(ValueError):
            devengo_por_100("ACT/366", D("4"), D("2"), 2,
                            date(2026, 1, 1), date(2026, 2, 1), 31, 181)

    def test_la_convencion_de_mercado_es_solo_informativa(self):
        from dominio.valorizacion.convenciones import convencion_de_mercado_sugerida
        self.assertEqual(convencion_de_mercado_sugerida("CAD"), "ACT/365")
        self.assertIsNone(convencion_de_mercado_sugerida("XXX"))
