"""Cola de trabajos de reproceso. Un solo reproceso activo por portafolio."""
from __future__ import annotations

import queue
import threading
import traceback
from typing import Callable, Optional

from aplicacion.casos_uso import reproceso as caso_reproceso
from aplicacion.casos_uso.contexto import Contexto


class ColaReprocesos:
    """Ejecuta en segundo plano, en serie, con estado consultable."""

    def __init__(self, ruta_bd: str) -> None:
        self.ruta_bd = ruta_bd
        self._cola: "queue.Queue[int]" = queue.Queue()
        self._hilo: Optional[threading.Thread] = None
        self._activo: Optional[int] = None
        self._lock = threading.Lock()

    def encolar(self, reproceso_id: int) -> None:
        self._cola.put(reproceso_id)
        self._asegurar_hilo()

    def _asegurar_hilo(self) -> None:
        with self._lock:
            if self._hilo is None or not self._hilo.is_alive():
                self._hilo = threading.Thread(target=self._bucle, daemon=True,
                                              name="cola-reprocesos")
                self._hilo.start()

    def _bucle(self) -> None:
        ctx = Contexto.abrir(self.ruta_bd)
        while True:
            try:
                rid = self._cola.get(timeout=2)
            except queue.Empty:
                return
            self._activo = rid
            try:
                caso_reproceso.ejecutar(ctx, rid)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
            finally:
                self._activo = None
                self._cola.task_done()

    @property
    def activo(self) -> Optional[int]:
        return self._activo

    @property
    def en_espera(self) -> int:
        return self._cola.qsize()

    def esperar(self, timeout: Optional[float] = None) -> None:
        """Utilidad para tests y para el arranque con datos de ejemplo."""
        self._cola.join()
