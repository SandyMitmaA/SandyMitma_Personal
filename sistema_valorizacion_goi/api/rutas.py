"""Capa de presentacion: API REST v1. Ninguna regla de calculo vive aqui."""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Callable, Optional

from aplicacion.casos_uso import consultas, estado, precios, registro, reproceso, validaciones
from aplicacion.casos_uso.contexto import Contexto
from aplicacion.casos_uso.registro import ErrorValidacion
from dominio.configuracion import DEFECTOS
from dominio.fechas import a_iso, de_iso
from infraestructura.archivos.exportacion import a_csv, a_xlsx
from infraestructura.persistencia.repositorios import PORTAFOLIO
from infraestructura.trabajos.cola import ColaReprocesos

PREFIJO = "/api/v1"


class Respuesta:
    def __init__(self, cuerpo: Any = None, estado_http: int = 200,
                 tipo: str = "application/json; charset=utf-8",
                 binario: Optional[bytes] = None,
                 cabeceras: Optional[dict[str, str]] = None) -> None:
        self.cuerpo = cuerpo
        self.estado = estado_http
        self.tipo = tipo
        self.binario = binario
        self.cabeceras = cabeceras or {}


class Api:
    def __init__(self, ctx: Contexto, cola: ColaReprocesos) -> None:
        self.ctx = ctx
        self.cola = cola
        self.rutas: list[tuple[str, str, Callable]] = []
        self._registrar()

    def ruta(self, metodo: str, patron: str):
        def deco(fn):
            self.rutas.append((metodo, PREFIJO + patron, fn))
            return fn
        return deco

    def despachar(self, metodo: str, camino: str, consulta: dict,
                  cuerpo: bytes, cabeceras: dict) -> Optional[Respuesta]:
        for m, patron, fn in self.rutas:
            if m != metodo:
                continue
            partes_p = patron.strip("/").split("/")
            partes_c = camino.strip("/").split("/")
            if len(partes_p) != len(partes_c):
                continue
            params: dict[str, str] = {}
            ok = True
            for a, b in zip(partes_p, partes_c):
                if a.startswith("{") and a.endswith("}"):
                    params[a[1:-1]] = b
                elif a != b:
                    ok = False
                    break
            if ok:
                return fn(params, consulta, cuerpo, cabeceras)
        return None

    # --- utilidades -------------------------------------------------------
    @staticmethod
    def _json(cuerpo: bytes) -> dict:
        if not cuerpo:
            return {}
        return json.loads(cuerpo.decode("utf-8"))

    def _usuario(self, cabeceras: dict) -> str:
        return cabeceras.get("X-Usuario") or "analista"

    def _rango(self, consulta: dict) -> tuple[date, date]:
        p = self.ctx.parametros.leer()
        a, b = self.ctx.valorizacion.rango_disponible()
        desde = de_iso(consulta.get("desde")) or de_iso(a) or p.fecha_inicio_portafolio
        hasta = de_iso(consulta.get("hasta")) or de_iso(b) or p.fecha_inicio_portafolio
        return desde, hasta

    @staticmethod
    def _isines(consulta: dict) -> Optional[list[str]]:
        v = consulta.get("isines") or consulta.get("isin")
        if not v:
            return None
        return [x.strip().upper() for x in v.split(",") if x.strip()]

    # --- registro de rutas ------------------------------------------------
    def _registrar(self) -> None:  # noqa: C901
        ctx = self.ctx

        @self.ruta("GET", "/estado")
        def _(p, c, b, h):
            par = ctx.parametros.leer()
            a, z = ctx.valorizacion.rango_disponible()
            port = ctx.bd.uno("SELECT * FROM portafolio WHERE id=?", (PORTAFOLIO,))
            return Respuesta({
                "sistema": "Sistema de Valorizacion Interno - GOI",
                "portafolio": dict(port) if port else None,
                "parametros": par.a_mapa(),
                "parametros_disponibles": DEFECTOS,
                "rango_valorizado": {"desde": a, "hasta": z},
                "usuario": self._usuario(h),
                "cola": {"activo": self.cola.activo, "en_espera": self.cola.en_espera},
            })

        @self.ruta("PUT", "/parametros")
        def _(p, c, b, h):
            datos = self._json(b)
            ctx.parametros.escribir(datos, self._usuario(h))
            # Alterar un parametro no recalcula: marca y deja en la bandeja.
            marcadas = 0
            a, z = ctx.valorizacion.rango_disponible()
            if a and z:
                por_isin: dict[str, list[date]] = {}
                for f in ctx.valorizacion.vigentes(de_iso(a), de_iso(z)):
                    por_isin.setdefault(f["isin"], []).append(
                        de_iso(f["fecha_valorizacion"]))
                for isin, fechas in por_isin.items():
                    marcadas += ctx.desactualizadas.marcar(
                        fechas, isin, "Parametro alterado")
            ctx.bitacora.registrar("CAMBIO_PARAMETROS", self._usuario(h),
                                   entidad="parametro", detalle=datos)
            return Respuesta({"parametros": ctx.parametros.leer().a_mapa(),
                              "fechas_desactualizadas": marcadas})

        # --- pendientes ---------------------------------------------------
        @self.ruta("GET", "/pendientes")
        def _(p, c, b, h):
            return Respuesta(estado.bandeja_pendientes(ctx))

        # --- instrumentos -------------------------------------------------
        @self.ruta("GET", "/instrumentos")
        def _(p, c, b, h):
            incluir = c.get("incluir_eliminados") == "1"
            instr = ctx.instrumentos.listar(incluir)
            pos = ctx.posiciones.listar(incluir)
            return Respuesta({
                "instrumentos": [{
                    "isin": i.isin, "descripcion": i.descripcion, "moneda": i.moneda,
                    "tasa_cupon": str(i.tasa_cupon), "frecuencia": i.frecuencia,
                    "fecha_emision": a_iso(i.fecha_emision),
                    "fecha_vencimiento": a_iso(i.fecha_vencimiento),
                    "convencion": i.convencion,
                    "precio_expresado_en": i.precio_expresado_en,
                    "valor_redencion": str(i.valor_redencion),
                    "eliminado_en": i.eliminado_en,
                } for i in instr],
                "posiciones": [{
                    "id": x.id, "isin": x.isin, "nominal": str(x.nominal),
                    "fecha_alta": a_iso(x.fecha_alta), "eliminado_en": x.eliminado_en,
                } for x in pos],
                "estados": estado.estado_instrumentos(ctx),
            })

        @self.ruta("POST", "/instrumentos/calendario")
        def _(p, c, b, h):
            return Respuesta(registro.previsualizar_calendario(self._json(b)))

        @self.ruta("POST", "/instrumentos")
        def _(p, c, b, h):
            return Respuesta(registro.guardar_instrumento(ctx, self._json(b), self._usuario(h)))

        @self.ruta("GET", "/instrumentos/{isin}/impacto-eliminacion")
        def _(p, c, b, h):
            return Respuesta(registro.impacto_eliminacion_instrumento(ctx, p["isin"]))

        @self.ruta("DELETE", "/instrumentos/{isin}")
        def _(p, c, b, h):
            d = self._json(b)
            return Respuesta(registro.eliminar_instrumento(
                ctx, p["isin"], d.get("motivo", ""), self._usuario(h),
                bool(d.get("cascada"))))

        @self.ruta("POST", "/instrumentos/{isin}/reactivar")
        def _(p, c, b, h):
            return Respuesta(registro.reactivar_instrumento(ctx, p["isin"], self._usuario(h)))

        # --- posiciones ---------------------------------------------------
        @self.ruta("POST", "/posiciones")
        def _(p, c, b, h):
            return Respuesta(registro.guardar_posicion(ctx, self._json(b), self._usuario(h)))

        @self.ruta("GET", "/posiciones/{id}/impacto-eliminacion")
        def _(p, c, b, h):
            return Respuesta(registro.impacto_eliminacion_posicion(ctx, int(p["id"])))

        @self.ruta("DELETE", "/posiciones/{id}")
        def _(p, c, b, h):
            d = self._json(b)
            return Respuesta(registro.eliminar_posicion(
                ctx, int(p["id"]), d.get("motivo", ""), self._usuario(h)))

        @self.ruta("POST", "/posiciones/{id}/reactivar")
        def _(p, c, b, h):
            return Respuesta(registro.reactivar_posicion(ctx, int(p["id"]), self._usuario(h)))

        # --- precios ------------------------------------------------------
        @self.ruta("GET", "/precios")
        def _(p, c, b, h):
            return Respuesta({
                "filas": ctx.precios.filas(
                    c.get("isin"), de_iso(c.get("desde")), de_iso(c.get("hasta")),
                    c.get("incluir_eliminados") == "1"),
                "huerfanos": ctx.precios.huerfanos(),
            })

        @self.ruta("POST", "/precios/preview")
        def _(p, c, b, h):
            nombre = c.get("archivo", "carga.csv")
            return Respuesta(precios.previsualizar(ctx, nombre, b, c.get("isin", "")))

        @self.ruta("POST", "/precios/confirmar")
        def _(p, c, b, h):
            nombre = c.get("archivo", "carga.csv")
            return Respuesta(precios.confirmar(
                ctx, nombre, b, self._usuario(h), c.get("isin", ""),
                c.get("periodo_cerrado") == "1", c.get("justificacion", "")))

        @self.ruta("POST", "/precios/manual")
        def _(p, c, b, h):
            return Respuesta(precios.capturar_manual(
                ctx, self._json(b).get("filas", []), self._usuario(h)))

        @self.ruta("DELETE", "/precios/{id}")
        def _(p, c, b, h):
            return Respuesta(precios.eliminar_precio(
                ctx, int(p["id"]), self._json(b).get("motivo", ""), self._usuario(h)))

        @self.ruta("POST", "/precios/purgar-huerfanos")
        def _(p, c, b, h):
            d = self._json(b)
            return Respuesta(precios.purgar_huerfanos(
                ctx, d.get("isin", ""), self._usuario(h), d.get("motivo", "")))

        # --- reproceso ----------------------------------------------------
        @self.ruta("GET", "/reproceso/propuesta")
        def _(p, c, b, h):
            return Respuesta(reproceso.rango_propuesto(ctx))

        @self.ruta("POST", "/reproceso/impacto")
        def _(p, c, b, h):
            d = self._json(b)
            return Respuesta(reproceso.analisis_impacto(
                ctx, de_iso(d["desde"]), de_iso(d["hasta"]), d.get("isines")))

        @self.ruta("POST", "/reproceso")
        def _(p, c, b, h):
            d = self._json(b)
            rid = reproceso.encolar(
                ctx, de_iso(d["desde"]), de_iso(d["hasta"]), d.get("isines"),
                self._usuario(h), d.get("disparador", "manual"),
                bool(d.get("forzado")), d.get("justificacion_reapertura", ""))
            self.cola.encolar(rid)
            return Respuesta({"reproceso_id": rid, "estado": "pendiente"}, 202)

        @self.ruta("GET", "/reproceso")
        def _(p, c, b, h):
            return Respuesta({"reprocesos": reproceso.listar_reprocesos(ctx),
                              "cola": {"activo": self.cola.activo,
                                       "en_espera": self.cola.en_espera}})

        @self.ruta("GET", "/reproceso/{id}")
        def _(p, c, b, h):
            r = ctx.bd.uno("SELECT * FROM reproceso WHERE id=?", (int(p["id"]),))
            return Respuesta(dict(r) if r else None, 200 if r else 404)

        @self.ruta("GET", "/reproceso/{id}/reexpresion")
        def _(p, c, b, h):
            return Respuesta({"filas": reproceso.reporte_reexpresion(ctx, int(p["id"]))})

        # --- valorizacion -------------------------------------------------
        @self.ruta("GET", "/valorizacion")
        def _(p, c, b, h):
            d, z = self._rango(c)
            v = int(c["version"]) if c.get("version") else None
            return Respuesta(consultas.grilla(ctx, d, z, self._isines(c), v))

        @self.ruta("GET", "/puente")
        def _(p, c, b, h):
            d, z = self._rango(c)
            v = int(c["version"]) if c.get("version") else None
            return Respuesta(consultas.puente(ctx, d, z, self._isines(c), v))

        @self.ruta("GET", "/control")
        def _(p, c, b, h):
            d, z = self._rango(c)
            return Respuesta(consultas.consolidado(ctx, d, z, self._isines(c)))

        @self.ruta("GET", "/validaciones")
        def _(p, c, b, h):
            d, z = self._rango(c)
            return Respuesta(validaciones.panel(ctx, d, z))

        @self.ruta("GET", "/versiones")
        def _(p, c, b, h):
            if c.get("fecha"):
                return Respuesta({"versiones": ctx.valorizacion.versiones_de_fecha(
                    de_iso(c["fecha"]))})
            return Respuesta({"versiones": ctx.valorizacion.versiones()})

        @self.ruta("GET", "/comparar")
        def _(p, c, b, h):
            return Respuesta(consultas.comparar_versiones(
                ctx, de_iso(c["fecha"]), int(c["a"]), int(c["b"])))

        @self.ruta("GET", "/trazabilidad")
        def _(p, c, b, h):
            return Respuesta(consultas.trazabilidad(ctx, de_iso(c["fecha"]), c["isin"]))

        @self.ruta("GET", "/bitacora")
        def _(p, c, b, h):
            return Respuesta({"filas": ctx.bitacora.listar()})

        # --- periodos -----------------------------------------------------
        @self.ruta("GET", "/periodos")
        def _(p, c, b, h):
            return Respuesta({"cerrados": ctx.periodos.cerrados()})

        @self.ruta("POST", "/periodos/cerrar")
        def _(p, c, b, h):
            d = self._json(b)
            pid = ctx.periodos.cerrar(de_iso(d["desde"]), de_iso(d["hasta"]),
                                      self._usuario(h))
            ctx.bitacora.registrar("CIERRE_PERIODO", self._usuario(h), entidad="periodo",
                                   entidad_id=str(pid), rango_desde=de_iso(d["desde"]),
                                   rango_hasta=de_iso(d["hasta"]))
            return Respuesta({"periodo_id": pid})

        @self.ruta("POST", "/periodos/{id}/reabrir")
        def _(p, c, b, h):
            d = self._json(b)
            ctx.periodos.reabrir(int(p["id"]), self._usuario(h), d.get("justificacion", ""))
            ctx.bitacora.registrar("REAPERTURA_PERIODO", self._usuario(h), entidad="periodo",
                                   entidad_id=p["id"], detalle=d)
            return Respuesta({"reabierto": True})

        # --- exportacion --------------------------------------------------
        @self.ruta("GET", "/exportar/{vista}")
        def _(p, c, b, h):
            d, z = self._rango(c)
            v = int(c["version"]) if c.get("version") else None
            vista = p["vista"]
            if vista == "valorizacion":
                datos = consultas.grilla(ctx, d, z, self._isines(c), v)
                columnas, filas = datos["columnas"], datos["filas"]
            elif vista == "puente":
                datos = consultas.puente(ctx, d, z, self._isines(c), v)
                columnas, filas = datos["columnas"], datos["filas"]
            elif vista == "consolidado":
                filas = consultas.consolidado(ctx, d, z, self._isines(c), v)["filas"]
                columnas = list(filas[0].keys()) if filas else []
            elif vista == "precios":
                filas = ctx.precios.filas(c.get("isin"), d, z)
                columnas = list(filas[0].keys()) if filas else []
            else:
                return Respuesta({"error": f"Vista desconocida: {vista}"}, 404)
            titulo = f"{vista} | {a_iso(d)} a {a_iso(z)}"
            formato = (c.get("formato") or "csv").lower()
            nombre = f"goi-{vista}-{a_iso(d)}-{a_iso(z)}.{formato}"
            if formato == "xlsx":
                return Respuesta(
                    binario=a_xlsx(columnas, filas, titulo),
                    tipo="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    cabeceras={"Content-Disposition": f'attachment; filename="{nombre}"'})
            return Respuesta(
                binario=a_csv(columnas, filas, titulo), tipo="text/csv; charset=utf-8",
                cabeceras={"Content-Disposition": f'attachment; filename="{nombre}"'})
