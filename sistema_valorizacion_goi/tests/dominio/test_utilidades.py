"""Cierra las ramas del dominio que las pruebas de cifras no recorren."""
import dataclasses
import unittest
from datetime import date
from decimal import Decimal as D

from dominio.caja.caja import eventos_de_caja, saldo_origen_hasta
from dominio.configuracion import Parametros
from dominio.control.control_t0 import (
    REVISAR, SIN_QUIEBRE, UN_DIA_DE_DEVENGO, clasificar_quiebre,
)
from dominio.dinero import CERO, a_texto, dec, div, es_decimal, q
from dominio.fechas import a_iso, de_iso, dias_entre, es_dia_habil, rango_fechas
from dominio.modelos import DatoMercado, Posicion, Precio
from dominio.valorizacion.calendario import calendario_cupones
from dominio.valorizacion.motor import valorizar
from dominio.valorizacion.series import SeriePrecios
from tests.fixtures.datos import CA, LB, PARAMETROS, POS_CA, POS_LB, PRECIOS


class ClasificacionDelQuiebre(unittest.TestCase):
    def test_sin_quiebre(self):
        estado, residual = clasificar_quiebre(D("0.001"), D("500"), D("0.01"))
        self.assertEqual(estado, SIN_QUIEBRE)
        self.assertEqual(residual, D("500.001"))

    def test_un_dia_de_devengo(self):
        estado, residual = clasificar_quiebre(D("-6639.87"), D("6639.87"), D("0.01"))
        self.assertEqual(estado, UN_DIA_DE_DEVENGO)
        self.assertEqual(residual, CERO)

    def test_revisar(self):
        estado, _ = clasificar_quiebre(D("-1000"), D("6639.87"), D("0.01"))
        self.assertEqual(estado, REVISAR)


class AritmeticaDecimal(unittest.TestCase):
    def test_vacio_y_nulo_valen_cero(self):
        self.assertEqual(dec(None), CERO)
        self.assertEqual(dec(""), CERO)

    def test_rechaza_float_y_booleano(self):
        with self.assertRaises(TypeError):
            dec(1.5)
        with self.assertRaises(TypeError):
            dec(True)

    def test_es_decimal(self):
        self.assertTrue(es_decimal(D("1")))
        self.assertFalse(es_decimal("1"))

    def test_division_por_cero(self):
        self.assertEqual(div(D("10"), D("4")), D("2.5"))
        with self.assertRaises(ZeroDivisionError):
            div(D("1"), CERO)

    def test_cuantizacion_media_par(self):
        self.assertIsNone(q(None, 2))
        self.assertEqual(q(D("2.345"), 2), D("2.34"))
        self.assertEqual(q(D("2.355"), 2), D("2.36"))

    def test_a_texto(self):
        self.assertIsNone(a_texto(None))
        self.assertEqual(a_texto(D("1.5000")), "1.5")


class Fechas(unittest.TestCase):
    def test_dias_entre(self):
        self.assertEqual(dias_entre(date(2026, 1, 1), date(2026, 1, 31)), 30)
        self.assertEqual(dias_entre(date(2026, 1, 31), date(2026, 1, 1)), -30)

    def test_conversiones_iso(self):
        self.assertIsNone(a_iso(None))
        self.assertIsNone(de_iso(None))
        self.assertIsNone(de_iso(""))
        self.assertEqual(de_iso(date(2026, 5, 31)), date(2026, 5, 31))
        self.assertEqual(de_iso("2026-05-31T10:00:00"), date(2026, 5, 31))

    def test_dia_habil(self):
        self.assertFalse(es_dia_habil(date(2026, 5, 31)))   # domingo
        self.assertTrue(es_dia_habil(date(2026, 6, 1)))     # lunes

    def test_rango_de_fechas(self):
        self.assertEqual(len(list(rango_fechas(date(2026, 5, 31), date(2026, 7, 31)))), 62)


class Parametrizacion(unittest.TestCase):
    def test_booleanos_desde_texto(self):
        p = Parametros.desde_mapa({"incluir_caja": "si", "calcular_control_t0": "0"})
        self.assertTrue(p.incluir_caja)
        self.assertFalse(p.calcular_control_t0)

    def test_control_t0_usa_la_convencion_de_mercado(self):
        p = PARAMETROS.como_control_t0()
        self.assertEqual(p.desfase_devengo, 0)
        self.assertEqual(p.busqueda_cupon, "INCLUSIVA")
        self.assertFalse(p.calcular_control_t0)

    def test_el_mapa_es_serializable(self):
        m = PARAMETROS.a_mapa()
        self.assertEqual(m["incluir_caja"], "false")
        self.assertEqual(m["fecha_inicio_portafolio"], "2026-05-31")

    def test_sin_cuantizar_el_precio_local_cambia_la_cifra(self):
        p = dataclasses.replace(PARAMETROS, cuantizar_precio_local=False)
        v = valorizar(CA, POS_CA, date(2026, 7, 31),
                      DatoMercado(D("65.633020"), D("1.4028")), p)
        # Sin la cuantizacion declarada la cifra se aleja de la referencia.
        self.assertNotEqual(q(v.total_mv_base, 2), D("13162246.93"))
        self.assertEqual(q(v.total_mv_base, 2), D("13162247.00"))


class Caja(unittest.TestCase):
    def test_no_cobra_cupones_anteriores_al_alta(self):
        cal = calendario_cupones(LB.fecha_emision, LB.fecha_vencimiento, LB.frecuencia)
        tardia = Posicion(7, LB.isin, D("1000"), date(2026, 3, 1))
        eventos = eventos_de_caja(LB, tardia, cal, PARAMETROS)
        self.assertEqual([e.tipo for e in eventos], ["REDENCION"])

    def test_el_saldo_se_reconstruye_como_suma_de_cobros(self):
        cal = calendario_cupones(CA.fecha_emision, CA.fecha_vencimiento, CA.frecuencia)
        eventos = eventos_de_caja(CA, POS_CA, cal, PARAMETROS)
        self.assertEqual(saldo_origen_hasta(eventos, date(2026, 5, 31)), CERO)
        self.assertEqual(saldo_origen_hasta(eventos, date(2026, 6, 1)), D("150000.000"))
        self.assertEqual(saldo_origen_hasta(eventos, date(2026, 12, 1)), D("300000.000"))


class Series(unittest.TestCase):
    def test_expone_sus_fechas(self):
        s = SeriePrecios(PRECIOS[CA.isin])
        self.assertEqual([f.isoformat() for f in s.fechas],
                         ["2026-05-31", "2026-06-01", "2026-07-31"])

    def test_sin_ningun_tipo_de_cambio_disponible(self):
        s = SeriePrecios([Precio(date(2026, 5, 31), CA.isin, D("67.2"), None)])
        m = s.resolver(date(2026, 5, 31), 4)
        self.assertIsNone(m.tipo_cambio)
        self.assertIn("Tipo de cambio", m.error)

    def test_sin_precio_previo_para_arrastrar(self):
        s = SeriePrecios([Precio(date(2026, 6, 10), CA.isin, D("67.2"), D("1.38"))])
        m = s.resolver(date(2026, 6, 1), 4)
        self.assertIsNone(m.precio)
        self.assertIn("Sin precio previo", m.error)
