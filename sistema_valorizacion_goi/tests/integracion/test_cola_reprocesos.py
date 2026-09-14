from datetime import date
from decimal import Decimal as D

from aplicacion.casos_uso import reproceso as rp
from infraestructura.persistencia.semilla import sembrar
from infraestructura.trabajos.cola import ColaReprocesos
from tests.integracion.base import ConBaseDeDatos

DESDE, HASTA = date(2026, 5, 31), date(2026, 7, 31)


class Cola(ConBaseDeDatos):
    def test_ejecuta_en_segundo_plano_y_en_serie(self):
        sembrar(self.ctx)
        cola = ColaReprocesos(self.ruta)
        ids = [rp.encolar(self.ctx, DESDE, HASTA, None, "test") for _ in range(3)]
        for i in ids:
            cola.encolar(i)
        cola.esperar()
        estados = [self.ctx.bd.uno("SELECT estado FROM reproceso WHERE id=?", (i,))["estado"]
                   for i in ids]
        self.assertEqual(estados, ["terminado"] * 3)

    def test_reprocesar_dos_veces_no_genera_version_nueva(self):
        sembrar(self.ctx)
        cola = ColaReprocesos(self.ruta)
        for _ in range(2):
            cola.encolar(rp.encolar(self.ctx, DESDE, HASTA, None, "test"))
        cola.esperar()
        self.assertEqual(len(self.ctx.valorizacion.versiones()), 1)

    def test_el_reproceso_es_transaccional(self):
        sembrar(self.ctx)
        rid = rp.encolar(self.ctx, DESDE, HASTA, None, "test")
        # Un fallo durante el calculo deja el reproceso en error y no publica nada.
        self.ctx.bd.ejecutar("UPDATE instrumento SET frecuencia=0 WHERE isin='CA135087M276'")
        with self.assertRaises(Exception):
            rp.ejecutar(self.ctx, rid)
        r = self.ctx.bd.uno("SELECT * FROM reproceso WHERE id=?", (rid,))
        self.assertEqual(r["estado"], "error")
        self.assertEqual(self.ctx.valorizacion.vigentes(DESDE, HASTA), [])
