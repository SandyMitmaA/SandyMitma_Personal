import unittest
from datetime import date
from decimal import Decimal as D

from dominio.dinero import q
from dominio.modelos import DatoMercado
from dominio.valorizacion.motor import valorizar, vigente
from tests.fixtures.datos import (
    CA, LB, PARAMETROS, POS_CA, POS_LB, POS_QY, QY, TOLERANCIA,
)

# Cada fila de la tabla de resultados esperados de la Parte IV es un caso.
FILAS_ESPERADAS = [
    # fecha, instrumento, posicion, precio, tc,
    # f_devengo, ult_cupon, prox_cupon, dias, periodo, devengo100, sec, dev, total
    (date(2026, 5, 31), CA, POS_CA, "67.2254419008982", "1.3804",
     "2026-06-01", "2025-12-01", "2026-06-01", 182, 182,
     "0.75000000", "13445088.38", "108664.16", "13553752.54"),
    (date(2026, 5, 31), LB, POS_LB, "100.105469", "1",
     "2026-06-01", "2026-01-31", "2026-07-31", 121, 181,
     "1.46236188", "50052734.50", "731180.94", "50783915.44"),
    (date(2026, 6, 30), QY, POS_QY, "99.949219", "1",
     "2026-07-01", "2026-06-30", "2026-12-31", 1, 184,
     "0.01120924", "49974609.50", "5604.62", "49980214.12"),
    (date(2026, 7, 30), LB, POS_LB, "99.988281", "1",
     "2026-07-31", "2026-01-31", "2026-07-31", 181, 181,
     "2.18750000", "49994140.50", "1093750.00", "51087890.50"),
]


class ResultadosEsperados(unittest.TestCase):
    def test_cada_fila_de_la_parte_iv(self):
        for caso in FILAS_ESPERADAS:
            (f, instr, pos, precio, tc, fdev, ult, prox, dias, periodo,
             d100, sec, dev, total) = caso
            with self.subTest(fecha=f, isin=instr.isin):
                v = valorizar(instr, pos, f, DatoMercado(D(precio), D(tc)), PARAMETROS)
                self.assertEqual(v.fecha_devengo.isoformat(), fdev)
                self.assertEqual(v.ultimo_cupon.isoformat(), ult)
                self.assertEqual(v.proximo_cupon.isoformat(), prox)
                self.assertEqual(v.dias_transcurridos, dias)
                self.assertEqual(v.dias_periodo, periodo)
                self.assertEqual(q(v.devengo_por_100, 8), D(d100))
                self.assertLessEqual(abs(v.security_mv_base - D(sec)), TOLERANCIA)
                self.assertLessEqual(abs(v.devengo_base - D(dev)), TOLERANCIA)
                self.assertLessEqual(abs(v.total_mv_base - D(total)), TOLERANCIA)

    def test_precio_implicito_en_moneda_local(self):
        v = valorizar(CA, POS_CA, date(2026, 5, 31),
                      DatoMercado(D("67.2254419008982"), D("1.3804")), PARAMETROS)
        # Confirma que el precio del proveedor llega en moneda base.
        self.assertEqual(q(v.precio_local, 3), D("92.798"))

    def test_devengo_sobre_fecha_de_cupon_da_el_periodo_completo(self):
        v = valorizar(CA, POS_CA, date(2026, 5, 31),
                      DatoMercado(D("67.2254419008982"), D("1.3804")), PARAMETROS)
        self.assertEqual(q(v.devengo_por_100, 8), D("0.75000000"))
        self.assertNotEqual(v.devengo_por_100, 0)

    def test_devengo_sobre_el_vencimiento_da_el_periodo_completo(self):
        v = valorizar(LB, POS_LB, date(2026, 7, 30),
                      DatoMercado(D("99.988281"), D("1")), PARAMETROS)
        self.assertEqual(q(v.devengo_por_100, 8), D("2.18750000"))
        self.assertLess(v.dias_periodo, 400)  # ninguna fecha de relleno se filtra

    def test_guarda_de_vencimiento(self):
        v = valorizar(LB, POS_LB, date(2026, 8, 15),
                      DatoMercado(D("99.9"), D("1")), PARAMETROS)
        self.assertEqual(v.dias_transcurridos, 0)
        self.assertEqual(v.dias_periodo, 0)
        self.assertEqual(v.devengo_por_100, 0)
        self.assertFalse(v.vigente)


class Vigencia(unittest.TestCase):
    def test_sale_de_cartera_el_dia_del_vencimiento(self):
        self.assertTrue(vigente(LB, POS_LB, date(2026, 7, 30), False))
        self.assertFalse(vigente(LB, POS_LB, date(2026, 7, 31), False))

    def test_valorizar_vencido_a_redencion_extiende_la_vigencia(self):
        self.assertTrue(vigente(LB, POS_LB, date(2026, 7, 31), True))

    def test_antes_del_alta_no_esta_vigente(self):
        self.assertFalse(vigente(QY, POS_QY, date(2026, 6, 29), False))
        self.assertTrue(vigente(QY, POS_QY, date(2026, 6, 30), False))


class CasosDeBorde(unittest.TestCase):
    def test_tipo_de_cambio_en_cero(self):
        v = valorizar(CA, POS_CA, date(2026, 5, 31),
                      DatoMercado(D("67.22"), D("0")), PARAMETROS)
        self.assertIn("Tipo de cambio", v.error)
        self.assertEqual(v.total_mv_base, 0)

    def test_fecha_vigente_sin_precio(self):
        v = valorizar(CA, POS_CA, date(2026, 5, 31),
                      DatoMercado(None, D("1.3804")), PARAMETROS)
        self.assertTrue(v.error)
        self.assertEqual(v.total_mv_base, 0)

    def test_dato_imputado_viaja_marcado(self):
        m = DatoMercado(D("67.22"), D("1.3804"), precio_imputado=True,
                        fecha_origen_precio=date(2026, 5, 29), dias_arrastre_precio=2)
        v = valorizar(CA, POS_CA, date(2026, 5, 31), m, PARAMETROS)
        self.assertTrue(v.precio_imputado)
        self.assertEqual(v.dias_arrastre_precio, 2)

    def test_valorizacion_a_redencion(self):
        import dataclasses
        p = dataclasses.replace(PARAMETROS, valorizar_vencido_a_redencion=True)
        v = valorizar(LB, POS_LB, date(2026, 7, 31),
                      DatoMercado(D("1.00"), D("1")), p)
        self.assertTrue(v.vigente)
        self.assertTrue(v.a_redencion)
        # Ignora el precio de mercado y usa el valor de redencion.
        self.assertEqual(v.precio_local, D("100"))
        self.assertEqual(q(v.devengo_por_100, 4), D("2.1875"))
        self.assertLessEqual(abs(v.total_mv_base - D("51093750")), TOLERANCIA)

    def test_alta_en_la_fecha_de_emision_devenga_un_dia(self):
        from dominio.modelos import Posicion
        pos = Posicion(9, QY.isin, D("50000000"), QY.fecha_emision)
        v = valorizar(QY, pos, QY.fecha_emision, DatoMercado(D("100"), D("1")), PARAMETROS)
        self.assertEqual(v.dias_transcurridos, 1)


class PrecisionDecimal(unittest.TestCase):
    def test_ningun_monto_atraviesa_el_motor_como_float(self):
        from decimal import Decimal

        v = valorizar(CA, POS_CA, date(2026, 5, 31),
                      DatoMercado(D("67.2254419008982"), D("1.3804")), PARAMETROS)
        montos = [v.devengo_por_100, v.precio_local, v.tipo_cambio, v.security_mv_local,
                  v.devengo_local, v.total_mv_local, v.fx, v.security_mv_base,
                  v.devengo_base, v.total_mv_base, v.nominal, v.cupon_por_periodo]
        for m in montos:
            self.assertIsInstance(m, Decimal)
            self.assertNotIsInstance(m, float)

    def test_el_motor_rechaza_un_float_en_la_entrada(self):
        from dominio.dinero import dec
        with self.assertRaises(TypeError):
            dec(1.5)
