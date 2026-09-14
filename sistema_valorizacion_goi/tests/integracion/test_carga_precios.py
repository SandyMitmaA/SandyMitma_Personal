import unittest
from datetime import date
from decimal import Decimal as D

from aplicacion.casos_uso import precios, registro
from infraestructura.archivos.exportacion import a_csv, a_xlsx
from infraestructura.archivos.parseo import ErrorArchivo, leer
from infraestructura.persistencia.semilla import MAESTRA, POSICIONES, PARAMETROS
from tests.integracion.base import ConBaseDeDatos

ARCHIVO = b"""fecha,isin,precio,tipo_cambio
2026-05-31,CA135087M276,67.2254419008982,1.3804
2026-06-01,CA135087M276,66.897249,1.3849
"""

CON_DUPLICADOS = ARCHIVO + b"""2026-05-31,CA135087M276,67.2254419008982,1.3804
2026-06-01,CA135087M276,66.897249,1.3849
"""

CON_TC_CERO = b"""fecha,isin,precio,tipo_cambio
2026-06-02,CA135087M276,66.5,0
"""


class CargaDePrecios(ConBaseDeDatos):
    def setUp(self):
        super().setUp()
        self.ctx.parametros.escribir(PARAMETROS, "t")
        for m in MAESTRA:
            registro.guardar_instrumento(self.ctx, m, "t")
        for p in POSICIONES:
            registro.guardar_posicion(self.ctx, p, "t")

    def test_preview_distingue_nuevas_identicas_y_en_conflicto(self):
        precios.confirmar(self.ctx, "a.csv", ARCHIVO, "t")
        modificado = ARCHIVO.replace(b"66.897249", b"66.900000")
        vista = precios.previsualizar(self.ctx, "b.csv", modificado)
        self.assertEqual(vista["resumen"]["identicas"], 1)
        self.assertEqual(vista["resumen"]["conflicto"], 1)
        conflicto = next(f for f in vista["filas"] if f["estado"] == "conflicto")
        self.assertEqual(conflicto["precio_anterior"], "66.897249")
        self.assertEqual(conflicto["precio"], "66.900000")

    def test_rechaza_duplicados_del_propio_archivo_no_los_suma(self):
        vista = precios.previsualizar(self.ctx, "dup.csv", CON_DUPLICADOS)
        self.assertEqual(vista["resumen"]["duplicados_internos"], 2)
        self.assertEqual(vista["resumen"]["rechazadas"], 2)
        precios.confirmar(self.ctx, "dup.csv", CON_DUPLICADOS, "t")
        self.assertEqual(len(self.ctx.precios.por_instrumento("CA135087M276")), 2)

    def test_la_carga_es_idempotente(self):
        a = precios.confirmar(self.ctx, "a.csv", ARCHIVO, "t")
        b = precios.confirmar(self.ctx, "a.csv", ARCHIVO, "t")
        self.assertFalse(a["idempotente"])
        self.assertTrue(b["idempotente"])
        self.assertEqual(len(self.ctx.precios.por_instrumento("CA135087M276")), 2)

    def test_avisa_de_tipo_de_cambio_en_cero(self):
        vista = precios.previsualizar(self.ctx, "tc.csv", CON_TC_CERO)
        self.assertEqual(vista["resumen"]["tipo_cambio_en_cero"], 1)
        self.assertTrue(any("imputado" in m for m in vista["filas"][0]["mensajes"]))

    def test_muestra_el_precio_implicito_en_moneda_local(self):
        vista = precios.previsualizar(self.ctx, "a.csv", ARCHIVO)
        fila = vista["filas"][0]
        self.assertEqual(fila["precio_expresado_en"], "BASE")
        self.assertEqual(fila["precio_local_implicito"], "92.798")

    def test_informa_la_cobertura_resultante(self):
        vista = precios.previsualizar(self.ctx, "a.csv", ARCHIVO)
        cobertura = next(c for c in vista["cobertura"] if c["isin"] == "CA135087M276")
        self.assertEqual(cobertura["rango_desde"], "2026-05-31")
        self.assertGreater(cobertura["faltantes"], 0)

    def test_la_carga_no_dispara_recalculo_pero_marca_las_fechas(self):
        r = precios.confirmar(self.ctx, "a.csv", ARCHIVO, "t")
        self.assertEqual(r["fechas_desactualizadas"], 2)
        self.assertEqual(len(self.ctx.valorizacion.vigentes(
            date(2026, 5, 31), date(2026, 7, 31))), 0)

    def test_eliminar_un_precio_deja_cobertura_parcial(self):
        precios.confirmar(self.ctx, "a.csv", ARCHIVO, "t")
        fila = self.ctx.precios.filas("CA135087M276")[0]
        r = precios.eliminar_precio(self.ctx, fila["id"], "capturado mal", "t")
        self.assertTrue(r["eliminado"])
        self.assertEqual(len(self.ctx.precios.por_instrumento("CA135087M276")), 1)

    def test_captura_manual_usa_la_misma_ruta(self):
        r = precios.capturar_manual(self.ctx, [
            {"isin": "CA135087M276", "fecha": "2026-06-03", "precio": "66.5",
             "tipo_cambio": "1.385"}], "t")
        self.assertEqual(r["resumen"]["nuevas"], 1)


class FormatosDeArchivo(unittest.TestCase):
    def test_lee_csv_con_punto_y_coma_y_fecha_dd_mm_aaaa(self):
        datos = b"fecha;isin;precio;tipo_cambio\n31/05/2026;CA135087M276;67,22;1,3804\n"
        registros, _ = leer("x.csv", datos)
        self.assertEqual(registros[0]["isin"], "CA135087M276")

    def test_ida_y_vuelta_por_excel(self):
        b = a_xlsx(["fecha", "isin", "precio", "tipo_cambio"],
                   [{"fecha": "2026-05-31", "isin": "CA135087M276",
                     "precio": "67.2254419008982", "tipo_cambio": "1.3804"}], "prueba")
        registros, _ = leer("x.xlsx", b)
        self.assertEqual(registros[0]["precio"], "67.2254419008982")

    def test_ida_y_vuelta_por_csv_conserva_el_encabezado_del_sistema(self):
        b = a_csv(["fecha", "isin", "precio"],
                  [{"fecha": "2026-05-31", "isin": "CA135087M276", "precio": "67.22"}], "t")
        self.assertIn(b"Sistema de Valorizacion Interno - GOI", b)
        registros, _ = leer("x.csv", b)
        self.assertEqual(len(registros), 1)

    def test_archivo_sin_columnas_obligatorias(self):
        with self.assertRaises(ErrorArchivo) as e:
            leer("x.csv", b"a,b\n1,2\n")
        self.assertIn("fecha", str(e.exception))
