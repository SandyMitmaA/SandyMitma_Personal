import tempfile
import unittest
from pathlib import Path

from aplicacion.casos_uso.contexto import Contexto


class ConBaseDeDatos(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.ruta = str(Path(self._dir.name) / "prueba.sqlite")
        self.ctx = Contexto.abrir(self.ruta)

    def tearDown(self):
        self._dir.cleanup()
