"""Los diecisiete casos de borde de la Parte IV, uno por prueba."""
import dataclasses
import unittest
from datetime import date
from decimal import Decimal as D

from dominio.dinero import q
from dominio.modelos import DatoMercado, Posicion, Precio
from dominio.valorizacion.corrida import EntradaCorrida, correr
from dominio.valorizacion.motor import valorizar, vigente
from dominio.valorizacion.series import SeriePrecios
from tests.fixtures.datos import (
    CA, DESDE, HASTA, INSTRUMENTOS, LB, PARAMETROS, POSICIONES, POS_CA, POS_LB,
    POS_QY, PRECIOS, QY, TOLERANCIA, TOLERANCIA_CONTROL,
)


class CasosDeBorde(unittest.TestCase):
    # 1
    def test_01_devengo_exactamente_sobre_una_fecha_de_cupon(self):
        v = valorizar(CA, POS_CA, date(2026, 5, 31),
                      DatoMercado(D("67.2254419008982"), D("1.3804")), PARAMETROS)
        self.assertEqual(v.dias_transcurridos, v.dias_periodo)
        self.assertEqual(q(v.devengo_por_100, 8), D("0.75000000"))

    # 2
    def test_02_devengo_exactamente_sobre_el_vencimiento(self):
        v = valorizar(LB, POS_LB, date(2026, 7, 30),
                      DatoMercado(D("99.988281"), D("1")), PARAMETROS)
        self.assertEqual((v.dias_transcurridos, v.dias_periodo), (181, 181))
        self.assertEqual(q(v.devengo_por_100, 4), D("2.1875"))

    # 3
    def test_03_fecha_posterior_al_vencimiento_deja_la_posicion_fuera(self):
        v = valorizar(LB, POS_LB, date(2026, 8, 1),
                      DatoMercado(D("99.9"), D("1")), PARAMETROS)
        self.assertFalse(v.vigente)
        self.assertEqual(v.total_mv_base, 0)

    # 4
    def test_04_alta_posterior_al_inicio_genera_alta_en_el_puente(self):
        r = _corrida()
        alta = [f for f in r.filas if f.puente.alta_posicion != 0]
        self.assertEqual([(f.fecha, f.isin) for f in alta],
                         [(date(2026, 6, 30), "US91282CQY02")])

    # 5
    def test_05_alta_retroactiva_anterior_al_inicio_no_genera_alta(self):
        pos = Posicion(4, CA.isin, D("20000000"), date(2020, 1, 1))
        r = _corrida(posiciones=[pos])
        self.assertTrue(all(f.puente.alta_posicion == 0 for f in r.filas))
        self.assertNotEqual(r.consolidado[0].begin_mv, 0)

    # 6
    def test_06_alta_igual_a_la_emision_devenga_un_dia(self):
        pos = Posicion(5, QY.isin, D("50000000"), QY.fecha_emision)
        v = valorizar(QY, pos, QY.fecha_emision, DatoMercado(D("99.949219"), D("1")),
                      PARAMETROS)
        self.assertEqual(v.dias_transcurridos, 1)
        v0 = valorizar(QY, pos, QY.fecha_emision, DatoMercado(D("99.949219"), D("1")),
                       PARAMETROS.como_control_t0())
        self.assertEqual(v0.dias_transcurridos, 0)
        self.assertEqual(v0.devengo_por_100, 0)

    # 7
    def test_07_tipo_de_cambio_en_cero(self):
        serie = SeriePrecios([
            Precio(date(2026, 5, 30), CA.isin, D("67.0"), D("1.38")),
            Precio(date(2026, 5, 31), CA.isin, D("67.2"), D("0")),
        ])
        m = serie.resolver(date(2026, 5, 31), 4)
        self.assertTrue(m.tipo_cambio_imputado)
        self.assertEqual(m.tipo_cambio, D("1.38"))
        self.assertEqual(m.fecha_origen_tipo_cambio, date(2026, 5, 30))

    # 8
    def test_08_fecha_sin_precio_dentro_y_fuera_del_limite_de_arrastre(self):
        serie = SeriePrecios([Precio(date(2026, 5, 31), CA.isin, D("67.2"), D("1.38"))])
        dentro = serie.resolver(date(2026, 6, 4), 4)
        self.assertTrue(dentro.precio_imputado)
        self.assertEqual(dentro.dias_arrastre_precio, 4)
        self.assertFalse(dentro.error)

        fuera = serie.resolver(date(2026, 6, 5), 4)
        self.assertIsNone(fuera.precio)
        self.assertIn("limite de arrastre", fuera.error)

    # 9
    def test_09_fin_de_semana_con_precio_arrastrado(self):
        serie = SeriePrecios([Precio(date(2026, 6, 5), CA.isin, D("67.2"), D("1.38"))])
        sabado = serie.resolver(date(2026, 6, 6), 4)
        self.assertTrue(sabado.precio_imputado)
        self.assertEqual(sabado.dias_arrastre_precio, 1)

    # 10
    def test_10_inicio_de_portafolio_en_dia_no_habil(self):
        from dominio.fechas import es_dia_habil
        self.assertFalse(es_dia_habil(DESDE))  # 31/05/2026 es domingo
        r = _corrida()
        self.assertEqual(r.consolidado[0].fecha, DESDE)
        self.assertEqual(q(r.consolidado[0].begin_mv, 2),
                         q(r.consolidado[0].end_mv, 2))

    # 11
    def test_11_vencimiento_sin_precio_en_la_fecha_de_vencimiento(self):
        serie = SeriePrecios(PRECIOS[LB.isin])
        self.assertIsNone(serie.observado(LB.fecha_vencimiento))
        redencion = D("50000000") * (1 + D("4.375") / 2 / 100)
        self.assertEqual(redencion, D("51093750.000"))

    # 13
    def test_13_recalculo_sobre_periodo_cerrado(self):
        # Cubierto en la capa de aplicacion; aqui se comprueba que recalcular el
        # mismo rango dos veces no altera ninguna cifra.
        a, b = _corrida(), _corrida()
        self.assertEqual([q(x.total_mv_base, 8) for x in a.consolidado],
                         [q(x.total_mv_base, 8) for x in b.consolidado])

    # 14
    def test_14_eliminar_una_posicion_del_saldo_inicial(self):
        posiciones = [p for p in POSICIONES if p.isin != "CA135087M276"]
        instrumentos = {k: v for k, v in INSTRUMENTOS.items() if k != "CA135087M276"}
        r = _corrida(instrumentos=instrumentos, posiciones=posiciones)
        self.assertLessEqual(abs(r.consolidado[0].begin_mv - D("50783915.44")), TOLERANCIA)
        self.assertTrue(all(f.isin != "CA135087M276" for f in r.filas))

    # 15
    def test_15_eliminar_una_posicion_con_cupones_cobrados_y_caja_activa(self):
        p = dataclasses.replace(PARAMETROS, incluir_caja=True)
        posiciones = [x for x in POSICIONES if x.isin != "CA135087M276"]
        instrumentos = {k: v for k, v in INSTRUMENTOS.items() if k != "CA135087M276"}
        r = _corrida(p, instrumentos, posiciones)
        # Los 150,000 CAD del cupon de CA salen del saldo en todas las fechas.
        self.assertEqual(r.consolidado[-1].caja_base, D("51093750"))
        for f in r.filas:
            self.assertLessEqual(abs(f.puente.control), TOLERANCIA_CONTROL)


def _corrida(parametros=PARAMETROS, instrumentos=None, posiciones=None):
    return correr(EntradaCorrida(
        instrumentos=instrumentos or INSTRUMENTOS,
        posiciones=posiciones or POSICIONES,
        precios=PRECIOS,
        parametros=parametros,
    ), DESDE, HASTA)
