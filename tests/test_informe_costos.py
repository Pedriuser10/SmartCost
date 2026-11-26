"""Pruebas del informe de D5 (herramientas/informe_costos.py). Solo carpetas temporales."""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from decimal import Decimal as D

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "herramientas"))

import informe_costos as ic  # noqa: E402
from models import db  # noqa: E402


def _sha(ruta):
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class TestInforme(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def test_sqlite_compara_y_marca_pendientes_sin_modificar_la_base(self):
        ruta = os.path.join(self._tmp.name, db.NOMBRE_ARCHIVO)
        base = db.BaseLocal(ruta)
        harina = base.add_insumo("Harina", "kg", 1000, 0.1)        # precio de hoy: 1.000 por kg
        base.set_unidad_base(harina, "g")
        base.registrar_compra(harina, 25, "kg", 30000)             # reposición 1,2 $/g
        pan = base.add_plato("Pan", 1500, 100)
        base.add_insumo_a_plato(pan, harina, 0.2, "kg")
        viejo = base.add_plato("Antiguo", 900, 0)
        base.add_insumo_a_plato(viejo, harina, 0.2)                # unidad sin confirmar
        base.cerrar()
        for sufijo in ("-wal", "-shm"):                            # dejar solo el archivo principal
            if os.path.exists(ruta + sufijo):
                os.remove(ruta + sufijo)
        antes = _sha(ruta)

        filas = {f["plato"]: f for f in ic.filas_informe(ic._desde_sqlite(ruta))}
        # Hoy: 0,2 × 1.000 × 1,1 + 100 = 320 ; proyectado: 200 g × 1,2 × 1,1 + 100 = 364
        self.assertEqual((filas["Pan"]["actual"], filas["Pan"]["proyectado"], filas["Pan"]["diferencia"]),
                         (D("320.0"), D("364.00"), D("44.00")))
        self.assertIsNone(filas["Antiguo"]["proyectado"])
        self.assertEqual(filas["Antiguo"]["pendientes"], ["Harina"])
        self.assertEqual(_sha(ruta), antes, "el informe no modifica la base")

    def test_json_actual_muestra_todo_pendiente(self):
        ruta = os.path.join(self._tmp.name, "app.json")
        datos = {"insumos": [{"id": 1, "nombre": "Tomate", "unidad": "10kg", "precio": 1200, "merma_pct": 0.05}],
                 "platos": [{"id": 1, "nombre": "Ensalada", "precio_venta": 3000, "mano_obra": 200,
                             "ingredientes": [{"rel_id": 1, "insumo_id": 1, "cantidad": 0.25},
                                              {"rel_id": 2, "insumo_id": 99, "cantidad": 1}]},
                            {"id": 2, "nombre": "Vacío", "precio_venta": 0, "mano_obra": 0, "ingredientes": []}]}
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f)
        antes = _sha(ruta)
        salida = io.StringIO()
        filas = {f["plato"]: f for f in ic.imprimir(ic.filas_informe(ic._desde_json(ruta)), salida)}
        self.assertEqual(filas["Ensalada"]["actual"], D("515.0"), "0,25 × 1.200 × 1,05 + 200, como la app")
        self.assertIsNone(filas["Ensalada"]["proyectado"])
        self.assertIn("0 de 2 platos con costo proyectado completo", salida.getvalue())
        self.assertEqual(_sha(ruta), antes)


if __name__ == "__main__":
    unittest.main()
