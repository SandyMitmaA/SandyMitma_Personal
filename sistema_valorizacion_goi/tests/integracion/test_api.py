"""La capa de presentacion no contiene reglas de calculo: solo se comprueba el contrato."""
import json
import threading
import time
import urllib.error
import urllib.request
from decimal import Decimal as D

from dominio.dinero import dec
from infraestructura.persistencia.semilla import sembrar
from tests.integracion.base import ConBaseDeDatos

PUERTO = 8799
TOLERANCIA = D("0.005")


class ContratoDeLaApi(ConBaseDeDatos):
    def setUp(self):
        super().setUp()
        sembrar(self.ctx)
        from api.servidor import crear_servidor

        self.servidor, _ = crear_servidor(self.ruta, PUERTO)
        self.hilo = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.hilo.start()
        self.base = f"http://127.0.0.1:{PUERTO}"

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        super().tearDown()

    def get(self, camino):
        with urllib.request.urlopen(self.base + camino) as r:
            return json.loads(r.read())

    def post(self, camino, datos=None):
        req = urllib.request.Request(
            self.base + camino, data=json.dumps(datos or {}).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Usuario": "prueba"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    def test_ciclo_completo_por_http(self):
        estado = self.get("/api/v1/estado")
        self.assertEqual(estado["sistema"], "Sistema de Valorizacion Interno - GOI")

        r = self.post("/api/v1/reproceso", {"desde": "2026-05-31", "hasta": "2026-07-31"})
        for _ in range(200):
            est = self.get(f"/api/v1/reproceso/{r['reproceso_id']}")
            if est["estado"] in ("terminado", "error"):
                break
            time.sleep(0.05)
        self.assertEqual(est["estado"], "terminado")

        v = self.get("/api/v1/valorizacion?desde=2026-07-31&hasta=2026-07-31")
        total = dec(v["consolidado"][0]["total_mv_base"])
        self.assertLessEqual(abs(total - D("63212688.76")), TOLERANCIA)

        p = self.get("/api/v1/puente?desde=2026-05-31&hasta=2026-07-31")
        self.assertEqual(len(p["filas"]), 186)
        self.assertEqual(p["filas_con_control_no_cero"], [])

        c = self.get("/api/v1/control?desde=2026-05-31&hasta=2026-07-31")
        self.assertEqual(len(c["filas"]), 62)
        self.assertEqual({f["estado_quiebre"] for f in c["filas"]},
                         {"Quiebre equivale a un dia de devengo"})

        val = self.get("/api/v1/validaciones")
        self.assertEqual(val["resumen"]["alertas"], 0)

    def test_sirve_el_frontend_y_sus_modulos(self):
        for camino, tipo in [("/", "text/html"), ("/app.js", "text/javascript"),
                             ("/estilos/tokens.css", "text/css"),
                             ("/modulos/valorizacion.js", "text/javascript")]:
            with urllib.request.urlopen(self.base + camino) as r:
                self.assertEqual(r.status, 200)
                self.assertIn(tipo, r.headers["Content-Type"])

    def test_error_de_validacion_devuelve_422_con_el_campo(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.post("/api/v1/instrumentos", {"isin": "CORTO"})
        self.assertEqual(e.exception.code, 422)
        cuerpo = json.loads(e.exception.read())
        self.assertEqual(cuerpo["campo"], "isin")

    def test_exportacion_en_csv_y_excel(self):
        self.post("/api/v1/reproceso", {"desde": "2026-05-31", "hasta": "2026-05-31"})
        time.sleep(1.0)
        for formato, firma in (("csv", b"Sistema de Valorizacion"), ("xlsx", b"PK")):
            url = (f"{self.base}/api/v1/exportar/valorizacion?desde=2026-05-31"
                   f"&hasta=2026-05-31&formato={formato}")
            with urllib.request.urlopen(url) as r:
                cuerpo = r.read()
            self.assertTrue(cuerpo.startswith(firma) or firma in cuerpo[:200])
            self.assertIn("attachment", r.headers["Content-Disposition"])

    def test_ruta_inexistente(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.get("/api/v1/no-existe")
        self.assertEqual(e.exception.code, 404)
