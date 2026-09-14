"""La prueba de eliminacion con reproceso de la Parte IV, los ocho pasos."""
from datetime import date
from decimal import Decimal as D

from aplicacion.casos_uso import registro
from aplicacion.casos_uso import reproceso as rp
from dominio.dinero import dec
from infraestructura.persistencia.semilla import PARAMETROS, sembrar
from tests.integracion.base import ConBaseDeDatos

TOLERANCIA = D("0.005")
TOLERANCIA_CONTROL = D("0.0000001")
DESDE, HASTA = date(2026, 5, 31), date(2026, 7, 31)


class EliminacionConReproceso(ConBaseDeDatos):
    def setUp(self):
        super().setUp()
        sembrar(self.ctx)
        self.reprocesar()

    def reprocesar(self):
        return rp.ejecutar(self.ctx, rp.encolar(self.ctx, DESDE, HASTA, None, "test"))

    def total(self, f=HASTA):
        return self.ctx.valorizacion.total_portafolio(f, False)

    def posicion(self, isin):
        return next(p for p in self.ctx.posiciones.listar(True) if p.isin == isin)

    def test_los_ocho_pasos(self):
        self.assertLessEqual(abs(self.total() - D("63212688.76")), TOLERANCIA)
        qy = self.posicion("US91282CQY02")

        # 1 y 2. Analisis de impacto antes de confirmar.
        impacto = registro.impacto_eliminacion_posicion(self.ctx, qy.id)
        self.assertEqual(impacto["valorizaciones_afectadas"], 32)
        self.assertEqual(impacto["rango_valorizado_desde"], "2026-06-30")
        self.assertEqual(impacto["rango_valorizado_hasta"], "2026-07-31")
        self.assertLessEqual(
            abs(dec(impacto["total_actual_fin"]) - D("63212688.76")), TOLERANCIA)
        self.assertLessEqual(
            abs(dec(impacto["total_resultante_fin"]) - D("13162246.93")), TOLERANCIA)

        # 3. La eliminacion no recalcula: las 32 fechas van a pendientes.
        r = registro.eliminar_posicion(self.ctx, qy.id, "registrada por error", "test")
        self.assertEqual(r["fechas_desactualizadas"], 32)
        self.assertLessEqual(abs(self.total() - D("63212688.76")), TOLERANCIA)
        pendientes = self.ctx.desactualizadas.listar()
        self.assertEqual(len([p for p in pendientes if p["isin"] == "US91282CQY02"]), 32)

        # 4. Reproceso del rango.
        self.reprocesar()
        self.assertLessEqual(abs(self.total() - D("13162246.93")), TOLERANCIA)

        # 5. El control del puente sigue dando cero.
        for f in self.ctx.valorizacion.vigentes(DESDE, HASTA):
            self.assertLessEqual(abs(dec(f["control"] or 0)), TOLERANCIA_CONTROL)

        # 6. La serie de precios sigue existiendo.
        self.assertEqual(len(self.ctx.precios.por_instrumento("US91282CQY02")), 2)

        # 7. Reactivar y reprocesar, sin recargar precios.
        registro.reactivar_posicion(self.ctx, qy.id, "test")
        self.reprocesar()
        self.assertLessEqual(abs(self.total() - D("63212688.76")), TOLERANCIA)

        # 8. Eliminar la posicion que forma parte del saldo inicial.
        ca = self.posicion("CA135087M276")
        registro.eliminar_posicion(self.ctx, ca.id, "prueba de saldo inicial", "test")
        self.reprocesar()
        filas = self.ctx.valorizacion.vigentes(DESDE, DESDE)
        begin = sum((dec(f["begin_mv"] or 0) for f in filas), D(0))
        self.assertLessEqual(abs(begin - D("50783915.44")), TOLERANCIA)
        todas = self.ctx.valorizacion.vigentes(DESDE, HASTA)
        self.assertEqual([f for f in todas if f["isin"] == "CA135087M276"], [])
        self.assertTrue(all(dec(f["alta_posicion"] or 0) == 0
                            for f in todas if f["isin"] != "US91282CQY02"))

    # Caso de borde 16: eliminacion en cascada.
    def test_eliminacion_en_cascada_conserva_los_precios_como_huerfanos(self):
        impacto = registro.impacto_eliminacion_instrumento(self.ctx, "US91282CQY02")
        self.assertTrue(impacto["requiere_cascada"])
        self.assertEqual(impacto["precios_conservados"], 2)
        r = registro.eliminar_instrumento(self.ctx, "US91282CQY02", "error", "test",
                                          cascada=True)
        self.assertEqual(r["posiciones_eliminadas"], 1)
        huerfanos = self.ctx.precios.huerfanos()
        self.assertEqual([h["isin"] for h in huerfanos], ["US91282CQY02"])
        self.assertEqual(huerfanos[0]["n"], 2)

    # Caso de borde 17: reactivacion.
    def test_reactivar_un_instrumento_recupera_su_serie(self):
        registro.eliminar_instrumento(self.ctx, "US91282CQY02", "error", "test", cascada=True)
        registro.reactivar_instrumento(self.ctx, "US91282CQY02", "test")
        qy = self.posicion("US91282CQY02")
        registro.reactivar_posicion(self.ctx, qy.id, "test")
        self.reprocesar()
        self.assertLessEqual(abs(self.total() - D("63212688.76")), TOLERANCIA)
        self.assertEqual(self.ctx.precios.huerfanos(), [])

    # Caso de borde 13: recalculo sobre un periodo cerrado.
    def test_reprocesar_un_periodo_cerrado_exige_reapertura_justificada(self):
        self.ctx.periodos.cerrar(DESDE, date(2026, 6, 30), "test")
        with self.assertRaises(PermissionError):
            rp.encolar(self.ctx, DESDE, HASTA, None, "test")
        rid = rp.encolar(self.ctx, DESDE, HASTA, None, "test",
                         justificacion_reapertura="correccion de precio del proveedor")
        rp.ejecutar(self.ctx, rid)
        acciones = [b["accion"] for b in self.ctx.bitacora.listar()]
        self.assertIn("REAPERTURA_PERIODO", acciones)
        self.assertEqual(self.ctx.periodos.cerrados(), [])
