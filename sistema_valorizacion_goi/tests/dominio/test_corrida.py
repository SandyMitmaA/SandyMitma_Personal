"""Consolidados, puente, caja y control T+0 de la Parte IV."""
import dataclasses
import unittest
from datetime import date
from decimal import Decimal as D

from dominio.control.control_t0 import UN_DIA_DE_DEVENGO
from dominio.dinero import q
from dominio.valorizacion.corrida import EntradaCorrida, correr
from tests.fixtures.datos import (
    DESDE, HASTA, INSTRUMENTOS, PARAMETROS, POSICIONES, PRECIOS, TOLERANCIA,
    TOLERANCIA_CONTROL,
)


def corrida(parametros=PARAMETROS, instrumentos=None, posiciones=None):
    entrada = EntradaCorrida(
        instrumentos=instrumentos or INSTRUMENTOS,
        posiciones=posiciones or POSICIONES,
        precios=PRECIOS,
        parametros=parametros,
    )
    return correr(entrada, DESDE, HASTA)


class PortafolioConsolidado(unittest.TestCase):
    def setUp(self):
        self.r = corrida()
        self.por_fecha = {c.fecha: c for c in self.r.consolidado}

    def test_total_al_31_05(self):
        c = self.por_fecha[date(2026, 5, 31)]
        self.assertLessEqual(abs(c.total_mv_base - D("64337667.97")), TOLERANCIA)
        self.assertLessEqual(abs(c.total_mv_base_t0 - D("64331028.10")), TOLERANCIA)

    def test_total_al_31_07(self):
        c = self.por_fecha[date(2026, 7, 31)]
        self.assertLessEqual(abs(c.total_mv_base - D("63212688.76")), TOLERANCIA)
        self.assertLessEqual(abs(c.total_mv_base_t0 - D("63206499.83")), TOLERANCIA)

    def test_186_combinaciones_de_fecha_e_instrumento(self):
        self.assertEqual(len(self.r.filas), 186)
        self.assertEqual(len(self.r.consolidado), 62)

    def test_el_control_del_puente_da_cero_en_todas_las_filas(self):
        for f in self.r.filas:
            with self.subTest(fecha=f.fecha, isin=f.isin):
                self.assertLessEqual(abs(f.puente.control), TOLERANCIA_CONTROL)

    def test_begin_igual_a_end_en_la_fecha_de_inicio(self):
        c = self.por_fecha[DESDE]
        self.assertEqual(q(c.begin_mv, 2), q(c.end_mv, 2))

    def test_las_posiciones_iniciales_no_generan_alta(self):
        for f in self.r.filas:
            if f.isin != "US91282CQY02":
                self.assertEqual(f.puente.alta_posicion, 0, f"{f.fecha} {f.isin}")

    def test_el_alta_posterior_al_inicio_si_genera_alta(self):
        alta = [f for f in self.r.filas
                if f.isin == "US91282CQY02" and f.puente.alta_posicion != 0]
        self.assertEqual(len(alta), 1)
        self.assertEqual(alta[0].fecha, date(2026, 6, 30))

    def test_los_62_dias_quiebran_por_un_dia_de_devengo(self):
        for c in self.r.consolidado:
            with self.subTest(fecha=c.fecha):
                self.assertEqual(c.estado_quiebre, UN_DIA_DE_DEVENGO)
                self.assertEqual(q(c.residual, 2), D("0.00"))

    def test_cupon_de_ca_al_01_06(self):
        f = next(x for x in self.r.filas
                 if x.fecha == date(2026, 6, 1) and x.isin == "CA135087M276")
        self.assertLessEqual(abs(f.puente.cupon_pagado - D("108311.07")), TOLERANCIA)


class ConCaja(unittest.TestCase):
    def setUp(self):
        self.r = corrida(dataclasses.replace(PARAMETROS, incluir_caja=True))
        self.por_fecha = {c.fecha: c for c in self.r.consolidado}

    def test_end_mv_y_efectivo_al_31_07(self):
        c = self.por_fecha[date(2026, 7, 31)]
        self.assertLessEqual(abs(c.caja_base - D("51200679.00")), TOLERANCIA)
        self.assertLessEqual(abs(c.end_mv - D("114413367.76")), TOLERANCIA)
        self.assertLessEqual(
            abs(c.total_mv_base_t0 + c.caja_base - D("114407178.83")), TOLERANCIA)

    def test_el_control_sigue_dando_cero_con_caja(self):
        for f in self.r.filas:
            with self.subTest(fecha=f.fecha, isin=f.isin):
                self.assertLessEqual(abs(f.puente.control), TOLERANCIA_CONTROL)

    def test_la_redencion_usa_el_nominal_de_la_posicion(self):
        f = next(x for x in self.r.filas
                 if x.fecha == date(2026, 7, 31) and x.isin == "US91282CLB53")
        self.assertEqual(f.caja_origen, D("51093750"))


class Idempotencia(unittest.TestCase):
    def test_reejecutar_produce_el_mismo_resultado(self):
        a = corrida()
        b = corrida()
        self.assertEqual([f.valorizacion.como_dict() for f in a.filas],
                         [f.valorizacion.como_dict() for f in b.filas])


class Reproceso(unittest.TestCase):
    def test_sin_el_instrumento_nuevo_el_total_es_solo_del_bono_canadiense(self):
        instrumentos = {k: v for k, v in INSTRUMENTOS.items() if k != "US91282CQY02"}
        posiciones = [p for p in POSICIONES if p.isin != "US91282CQY02"]
        r = corrida(instrumentos=instrumentos, posiciones=posiciones)
        self.assertLessEqual(
            abs(r.consolidado[-1].total_mv_base - D("13162246.93")), TOLERANCIA)

    def test_eliminar_la_posicion_del_saldo_inicial_cambia_el_begin_mv(self):
        instrumentos = {k: v for k, v in INSTRUMENTOS.items() if k != "CA135087M276"}
        posiciones = [p for p in POSICIONES if p.isin != "CA135087M276"]
        r = corrida(instrumentos=instrumentos, posiciones=posiciones)
        self.assertLessEqual(
            abs(r.consolidado[0].begin_mv - D("50783915.44")), TOLERANCIA)
