from datetime import date

from aplicacion.casos_uso import estado, registro
from aplicacion.casos_uso.registro import ErrorValidacion
from infraestructura.persistencia.semilla import MAESTRA, PARAMETROS, POSICIONES
from tests.integracion.base import ConBaseDeDatos


class Registro(ConBaseDeDatos):
    def setUp(self):
        super().setUp()
        self.ctx.parametros.escribir(PARAMETROS, "t")

    def test_al_guardar_muestra_el_calendario_derivado(self):
        r = registro.guardar_instrumento(self.ctx, MAESTRA[2], "t")
        self.assertEqual(r["calendario"][:2], ["2026-06-30", "2026-12-31"])

    def test_valida_cada_campo_de_la_maestra(self):
        malo = dict(MAESTRA[0], isin="CORTO")
        with self.assertRaises(ErrorValidacion) as e:
            registro.guardar_instrumento(self.ctx, malo, "t")
        self.assertEqual(e.exception.campo, "isin")

        malo = dict(MAESTRA[0], fecha_vencimiento="2020-01-01")
        with self.assertRaises(ErrorValidacion) as e:
            registro.guardar_instrumento(self.ctx, malo, "t")
        self.assertEqual(e.exception.campo, "fecha_vencimiento")

        malo = dict(MAESTRA[0], convencion="ACT/366")
        with self.assertRaises(ErrorValidacion) as e:
            registro.guardar_instrumento(self.ctx, malo, "t")
        self.assertEqual(e.exception.campo, "convencion")

    def test_rechaza_alta_posterior_al_vencimiento(self):
        registro.guardar_instrumento(self.ctx, MAESTRA[1], "t")
        with self.assertRaises(ErrorValidacion) as e:
            registro.guardar_posicion(self.ctx, {
                "isin": "US91282CLB53", "nominal": "1000", "fecha_alta": "2027-01-01"}, "t")
        self.assertEqual(e.exception.campo, "fecha_alta")

    def test_informa_el_efecto_del_alta_sobre_el_puente(self):
        registro.guardar_instrumento(self.ctx, MAESTRA[0], "t")
        r = registro.guardar_posicion(self.ctx, POSICIONES[0], "t")
        self.assertTrue(r["parte_del_saldo_inicial"])
        self.assertFalse(r["genera_alta_en_puente"])

        registro.guardar_instrumento(self.ctx, MAESTRA[2], "t")
        r = registro.guardar_posicion(self.ctx, POSICIONES[2], "t")
        self.assertFalse(r["parte_del_saldo_inicial"])
        self.assertTrue(r["genera_alta_en_puente"])

    def test_reporta_la_desviacion_de_convencion_sin_alterarla(self):
        r = registro.guardar_instrumento(self.ctx, MAESTRA[0], "t")
        self.assertEqual(r["desviacion_convencion"],
                         {"declarada": "ACT/ACT", "uso_de_mercado": "ACT/365"})
        self.assertEqual(self.ctx.instrumentos.obtener("CA135087M276").convencion, "ACT/ACT")

    def test_el_motivo_de_eliminacion_es_obligatorio(self):
        registro.guardar_instrumento(self.ctx, MAESTRA[0], "t")
        pos = registro.guardar_posicion(self.ctx, POSICIONES[0], "t")
        with self.assertRaises(ErrorValidacion):
            registro.eliminar_posicion(self.ctx, pos["posicion_id"], "  ", "t")

    def test_eliminar_un_instrumento_con_posiciones_exige_cascada(self):
        registro.guardar_instrumento(self.ctx, MAESTRA[0], "t")
        registro.guardar_posicion(self.ctx, POSICIONES[0], "t")
        with self.assertRaises(ErrorValidacion) as e:
            registro.eliminar_instrumento(self.ctx, "CA135087M276", "error", "t")
        self.assertEqual(e.exception.campo, "cascada")
        r = registro.eliminar_instrumento(self.ctx, "CA135087M276", "error", "t", cascada=True)
        self.assertEqual(r["posiciones_eliminadas"], 1)

    def test_la_eliminacion_es_logica_y_conserva_el_rastro(self):
        registro.guardar_instrumento(self.ctx, MAESTRA[0], "t")
        pos = registro.guardar_posicion(self.ctx, POSICIONES[0], "t")
        registro.eliminar_posicion(self.ctx, pos["posicion_id"], "registrada por error", "t")
        fila = self.ctx.posiciones.fila(pos["posicion_id"])
        self.assertIsNotNone(fila["eliminado_en"])
        self.assertEqual(fila["eliminado_por"], "t")
        self.assertEqual(fila["motivo_eliminacion"], "registrada por error")

    def test_estados_del_instrumento(self):
        registro.guardar_instrumento(self.ctx, MAESTRA[0], "t")
        e = estado.estado_instrumentos(self.ctx)[0]
        self.assertEqual(e["estado"], "Registrado")
        registro.guardar_posicion(self.ctx, POSICIONES[0], "t")
        e = estado.estado_instrumentos(self.ctx)[0]
        self.assertEqual(e["estado"], "Sin precios")

    def test_la_bandeja_enlaza_al_modulo_que_resuelve(self):
        registro.guardar_instrumento(self.ctx, MAESTRA[0], "t")
        registro.guardar_posicion(self.ctx, POSICIONES[0], "t")
        b = estado.bandeja_pendientes(self.ctx)
        p = next(x for x in b["pendientes"] if x["isin"] == "CA135087M276")
        self.assertEqual(p["tipo"], "SIN_PRECIOS")
        self.assertEqual(p["modulo"], "precios")
