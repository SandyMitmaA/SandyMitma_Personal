"""La prueba de reproceso retroactivo de la Parte IV, completa, los siete pasos."""
from datetime import date
from decimal import Decimal as D

from aplicacion.casos_uso import precios, registro
from aplicacion.casos_uso import reproceso as rp
from dominio.dinero import dec, q
from infraestructura.persistencia.semilla import MAESTRA, PARAMETROS, POSICIONES
from tests.integracion.base import ConBaseDeDatos

TOLERANCIA = D("0.005")

PRECIOS_1 = b"""fecha,isin,precio,tipo_cambio
2026-05-31,CA135087M276,67.2254419008982,1.3804
2026-06-01,CA135087M276,66.897249,1.3849
2026-07-31,CA135087M276,65.633020,1.4028
2026-05-31,US91282CLB53,100.105469,1
2026-07-30,US91282CLB53,99.988281,1
"""
PRECIOS_2 = b"""fecha,isin,precio,tipo_cambio
2026-06-30,US91282CQY02,99.949219,1
2026-07-31,US91282CQY02,99.742188,1
"""
DESDE, HASTA = date(2026, 5, 31), date(2026, 7, 31)


class ReprocesoRetroactivo(ConBaseDeDatos):
    def total(self, f=HASTA):
        return self.ctx.valorizacion.total_portafolio(f, False)

    def reprocesar(self, desde=DESDE, hasta=HASTA, isines=None, forzado=False):
        rid = rp.encolar(self.ctx, desde, hasta, isines, "test", forzado=forzado)
        return rp.ejecutar(self.ctx, rid)

    def test_los_siete_pasos(self):
        self.ctx.parametros.escribir(PARAMETROS, "test")

        # 1. Solo CA y LB, con sus precios.
        for m in MAESTRA[:2]:
            registro.guardar_instrumento(self.ctx, m, "test")
        for p in POSICIONES[:2]:
            registro.guardar_posicion(self.ctx, p, "test")
        precios.confirmar(self.ctx, "p1.csv", PRECIOS_1, "test")
        self.reprocesar()
        self.assertLessEqual(abs(self.total() - D("13162246.93")), TOLERANCIA)

        # 2. Alta de US91282CQY02 con fecha anterior a hoy, y sus precios.
        registro.guardar_instrumento(self.ctx, MAESTRA[2], "test")
        alta = registro.guardar_posicion(self.ctx, POSICIONES[2], "test")
        precios.confirmar(self.ctx, "p2.csv", PRECIOS_2, "test")

        # 3. El sistema detecta 32 fechas afectadas, del 30/06 al 31/07.
        self.assertEqual(alta["fechas_desactualizadas"], 32)
        propuesta = rp.rango_propuesto(self.ctx)
        self.assertEqual(propuesta["desde"], "2026-06-30")
        self.assertEqual(propuesta["hasta"], "2026-07-31")
        self.assertEqual(propuesta["fechas_desactualizadas"], 32)

        # 4. Recalcula.
        resultado = self.reprocesar()
        self.assertLessEqual(abs(self.total() - D("63212688.76")), TOLERANCIA)

        # 5. El reporte de reexpresion lista las 32 fechas y atribuye la causa.
        reporte = rp.reporte_reexpresion(self.ctx, resultado["reproceso_id"])
        self.assertEqual(len(reporte), 32)
        self.assertEqual({r["causa"] for r in reporte},
                         {"Alta de instrumento o posicion"})
        self.assertEqual(min(r["fecha_valorizacion"] for r in reporte), "2026-06-30")
        self.assertEqual(max(r["fecha_valorizacion"] for r in reporte), "2026-07-31")
        for r in reporte:
            self.assertIsNotNone(r["valor_nuevo"])
            self.assertIsNotNone(r["diferencia_absoluta"])

        # 6. La valorizacion anterior sigue consultable como version previa.
        versiones = self.ctx.valorizacion.versiones_de_fecha(HASTA)
        self.assertEqual(len(versiones), 2)
        previa = self.ctx.valorizacion.vigentes(HASTA, HASTA, None, versiones[1]["id"])
        total_previo = sum((dec(f["total_mv_base"]) for f in previa), D(0))
        self.assertLessEqual(abs(total_previo - D("13162246.93")), TOLERANCIA)

        # 7. Recalcular otra vez no genera diferencia ni version nueva.
        otra = self.reprocesar()
        self.assertTrue(otra["sin_cambios"])
        self.assertIsNone(otra["version"])
        self.assertEqual(len(self.ctx.valorizacion.versiones_de_fecha(HASTA)), 2)

    def test_el_recalculo_forzado_versiona_aunque_nada_cambie(self):
        self.ctx.parametros.escribir(PARAMETROS, "test")
        for m in MAESTRA:
            registro.guardar_instrumento(self.ctx, m, "test")
        for p in POSICIONES:
            registro.guardar_posicion(self.ctx, p, "test")
        precios.confirmar(self.ctx, "p1.csv", PRECIOS_1, "test")
        precios.confirmar(self.ctx, "p2.csv", PRECIOS_2, "test")
        self.reprocesar()
        forzado = self.reprocesar(forzado=True)
        self.assertFalse(forzado["sin_cambios"])
        self.assertIsNotNone(forzado["version"])
        self.assertEqual(forzado["cambios"], 0)
