"""Contenedor de dependencias. Orquesta dominio e infraestructura."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from infraestructura.persistencia.db import BaseDatos
from infraestructura.persistencia.repo_valorizacion import RepoValorizacion
from infraestructura.persistencia.repositorios import (
    PORTAFOLIO,
    RepoBitacora,
    RepoDesactualizadas,
    RepoInstrumentos,
    RepoParametros,
    RepoPeriodos,
    RepoPosiciones,
    RepoPrecios,
)


@dataclass
class Contexto:
    bd: BaseDatos
    instrumentos: RepoInstrumentos
    posiciones: RepoPosiciones
    precios: RepoPrecios
    parametros: RepoParametros
    bitacora: RepoBitacora
    desactualizadas: RepoDesactualizadas
    periodos: RepoPeriodos
    valorizacion: RepoValorizacion

    @staticmethod
    def abrir(ruta: str | Path) -> "Contexto":
        bd = BaseDatos(ruta)
        bd.migrar()
        ctx = Contexto(
            bd=bd,
            instrumentos=RepoInstrumentos(bd),
            posiciones=RepoPosiciones(bd),
            precios=RepoPrecios(bd),
            parametros=RepoParametros(bd),
            bitacora=RepoBitacora(bd),
            desactualizadas=RepoDesactualizadas(bd),
            periodos=RepoPeriodos(bd),
            valorizacion=RepoValorizacion(bd),
        )
        ctx.asegurar_portafolio()
        return ctx

    def asegurar_portafolio(self) -> None:
        r = self.bd.uno("SELECT id FROM portafolio WHERE id=?", (PORTAFOLIO,))
        if r is None:
            p = self.parametros.leer()
            self.bd.ejecutar(
                "INSERT INTO portafolio (id, nombre, moneda_base, fecha_inicio) VALUES (?,?,?,?)",
                (PORTAFOLIO, "Cartera de renta fija GOI", p.moneda_base,
                 p.fecha_inicio_portafolio.isoformat()),
            )
