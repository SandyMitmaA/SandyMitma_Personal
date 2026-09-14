from datetime import date
from decimal import Decimal as D

from aplicacion.casos_uso import precios, registro, validaciones
from aplicacion.casos_uso import reproceso as rp
from dominio.dinero import dec
from infraestructura.persistencia.semilla import sembrar
from tests.integracion.base import ConBaseDeDatos

DESDE, HASTA = date(2026, 5, 31), date(2026, 7, 31)


class PanelDeValidaciones(ConBaseDeDatos):
    def setUp(self):
        super().setUp()
        sembrar(self.ctx)
        rp.ejecutar(self.ctx, rp.encolar(self.ctx, DESDE, HASTA, None, "test"))
        self.panel = validaciones.panel(self.ctx, DESDE, HASTA)
        self.por_codigo = {v["codigo"]: v for v in self.panel["validaciones"]}

    def test_estan_las_trece_validaciones(self):
        self.assertEqual([v["codigo"] for v in self.panel["validaciones"]],
                         [str(i) for i in range(1, 14)])

    def test_el_control_del_puente_no_reporta_hallazgos(self):
        self.assertEqual(self.por_codigo["9"]["hallazgos"], 0)

    def test_ninguna_fecha_queda_en_revisar(self):
        self.assertEqual(self.por_codigo["8"]["hallazgos"], 0)

    def test_reporta_el_vencimiento_sin_precio_con_su_diferencia(self):
        d = self.por_codigo["5"]["detalle"][0]
        self.assertEqual(d["isin"], "US91282CLB53")
        self.assertEqual(dec(d["valor_redencion"]), D("51093750"))
        self.assertEqual(dec(d["ultima_valorizacion_mercado"]), D("51081847.68"))
        self.assertEqual(dec(d["diferencia"]), D("11902.32"))

    def test_reporta_la_desviacion_de_convencion_con_impacto_cuantificado(self):
        d = self.por_codigo["7"]["detalle"][0]
        self.assertEqual((d["isin"], d["declarada"], d["uso_de_mercado"]),
                         ("CA135087M276", "ACT/ACT", "ACT/365"))
        self.assertIsNotNone(d["impacto_moneda_base"])

    def test_marca_las_fechas_en_dia_no_habil(self):
        self.assertGreater(self.por_codigo["6"]["hallazgos"], 0)

    def test_distingue_los_datos_imputados_por_arrastre(self):
        detalle = self.por_codigo["3"]["detalle"]
        self.assertTrue(any("dias" in d for d in detalle))

    def test_detecta_series_huerfanas(self):
        self.assertEqual(self.por_codigo["13"]["hallazgos"], 0)
        registro.eliminar_instrumento(self.ctx, "US91282CQY02", "error", "test", cascada=True)
        panel = validaciones.panel(self.ctx, DESDE, HASTA)
        codigo13 = next(v for v in panel["validaciones"] if v["codigo"] == "13")
        self.assertEqual(codigo13["detalle"][0]["isin"], "US91282CQY02")

    def test_detecta_eliminaciones_pendientes_de_reprocesar(self):
        pos = next(p for p in self.ctx.posiciones.listar() if p.isin == "US91282CQY02")
        registro.eliminar_posicion(self.ctx, pos.id, "error", "test")
        panel = validaciones.panel(self.ctx, DESDE, HASTA)
        codigo12 = next(v for v in panel["validaciones"] if v["codigo"] == "12")
        self.assertEqual(codigo12["hallazgos"], 1)

    def test_detecta_precio_implicito_fuera_de_rango(self):
        # Un precio absurdo delata que la moneda declarada no es la correcta.
        precios.confirmar(self.ctx, "malo.csv",
                          b"fecha,isin,precio,tipo_cambio\n"
                          b"2026-06-15,CA135087M276,900,1.39\n", "test")
        rp.ejecutar(self.ctx, rp.encolar(self.ctx, DESDE, HASTA, None, "test"))
        panel = validaciones.panel(self.ctx, DESDE, HASTA)
        codigo4 = next(v for v in panel["validaciones"] if v["codigo"] == "4")
        self.assertGreater(codigo4["hallazgos"], 0)
        self.assertEqual(codigo4["nivel"], "alert")


class ConsolidadoYCaja(ConBaseDeDatos):
    """El saldo de caja solo entra al consolidado cuando el parametro lo activa."""

    def setUp(self):
        super().setUp()
        sembrar(self.ctx)
        rp.ejecutar(self.ctx, rp.encolar(self.ctx, DESDE, HASTA, None, "test"))

    def test_sin_caja_el_consolidado_no_muestra_saldo(self):
        from aplicacion.casos_uso import consultas
        c = consultas.consolidado(self.ctx, HASTA, HASTA)
        self.assertFalse(c["incluir_caja"])
        self.assertEqual(dec(c["filas"][0]["caja_base"]), D(0))
        self.assertEqual(dec(c["filas"][0]["end_mv"]),
                         dec(c["filas"][0]["total_mv_base"]))

    def test_con_caja_el_consolidado_suma_el_saldo_al_end_mv(self):
        from aplicacion.casos_uso import consultas
        self.ctx.parametros.escribir({"incluir_caja": "true"}, "test")
        rp.ejecutar(self.ctx, rp.encolar(self.ctx, DESDE, HASTA, None, "test"))
        c = consultas.consolidado(self.ctx, HASTA, HASTA)
        self.assertTrue(c["incluir_caja"])
        fila = c["filas"][0]
        self.assertLessEqual(abs(dec(fila["caja_base"]) - D("51200679.00")), D("0.005"))
        self.assertLessEqual(abs(dec(fila["end_mv"]) - D("114413367.76")), D("0.005"))
