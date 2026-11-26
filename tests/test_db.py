"""Pruebas de models/db.py. Ejecutar desde la raíz: python -m unittest discover -s tests -v

Solo usan carpetas temporales: nunca tocan los datos reales ni data/app.json.
"""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, rutas, storage  # noqa: E402


def _sin_fechas(valor):
    """Quita fecha_creacion para comparar JSON y SQLite (se generan en momentos distintos)."""
    if isinstance(valor, list):
        return [_sin_fechas(v) for v in valor]
    if isinstance(valor, dict):
        return {k: _sin_fechas(v) for k, v in valor.items() if k != "fecha_creacion"}
    return valor


class BaseTemporal(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self._tmp.name, db.NOMBRE_ARCHIVO)
        self.base = db.BaseLocal(self.ruta)

    def tearDown(self):
        self.base.cerrar()
        self._tmp.cleanup()

    def reabrir(self):
        self.base.cerrar()
        self.base = db.BaseLocal(self.ruta)


class TestEquivalenciaConJSON(BaseTemporal):
    """La misma secuencia de operaciones debe dar el mismo resultado que storage.py."""

    def setUp(self):
        super().setUp()
        rutas.configurar(self._tmp.name)
        os.makedirs(rutas.datos_dir(), exist_ok=True)

    def _secuencia(self, s):
        s.add_insumo("Tomate", "kg", 1200.0, 5.0)
        s.add_insumo("arroz", "10kg", 9000.0, 0.0)
        s.add_insumo("Ñame", "un", 300.0, 0.0)
        s.add_insumo("Aceite", "lt", 2500.0, 0.0)
        p1 = s.add_plato("Ensalada", 4500.0, 500.0, "ensalada.jpg")
        p2 = s.add_plato("arroz graneado", 3000.0, 300.0)
        s.add_insumo_a_plato(p1, 1, 0.25)
        s.add_insumo_a_plato(p1, 4, 0.02)
        s.add_insumo_a_plato(p2, 2, 0.1)
        s.add_insumo_a_plato(p2, 4, 0.01)
        s.update_insumo(1, "Tomate larga vida", "kg", 1300.0, 6.0)
        s.update_plato(p1, "Ensalada chilena", 4800.0, 550.0)          # sin imagen: conserva la foto
        s.update_plato(p2, "Arroz graneado", 3200.0, 300.0, "arroz.png")
        s.quitar_insumo_de_plato(2)
        s.delete_insumo(3)
        s.delete_insumo(4)                                               # sale de las dos recetas
        s.update_insumo(99, "no existe", "kg", 1.0, 0.0)                 # ids inexistentes: no pasa nada
        s.delete_plato(99)
        return p1, p2

    def test_misma_secuencia_mismo_resultado(self):
        p1j, p2j = self._secuencia(storage)
        p1s, p2s = self._secuencia(self.base)
        self.assertEqual((p1j, p2j), (p1s, p2s))
        self.assertEqual(_sin_fechas(storage.get_insumos()), _sin_fechas(self.base.get_insumos()))
        self.assertEqual(_sin_fechas(storage.get_platos()), _sin_fechas(self.base.get_platos()))
        for pid in (p1s, p2s, 99):
            self.assertEqual(_sin_fechas(storage.get_plato(pid)), _sin_fechas(self.base.get_plato(pid)))
            self.assertEqual(_sin_fechas(storage.get_insumos_de_plato(pid)),
                             _sin_fechas(self.base.get_insumos_de_plato(pid)))

    def test_borrar_plato_igual_que_json(self):
        for s in (storage, self.base):
            s.add_insumo("Sal", "kg", 800.0, 0.0)
            p = s.add_plato("Papas", 2000.0, 100.0)
            s.add_insumo_a_plato(p, 1, 0.01)
            s.delete_plato(p)
        self.assertEqual(_sin_fechas(storage.get_platos()), _sin_fechas(self.base.get_platos()))
        self.assertEqual(_sin_fechas(storage.get_insumos()), _sin_fechas(self.base.get_insumos()))


class TestPersistenciaYEsquema(BaseTemporal):
    def test_los_datos_sobreviven_al_reabrir(self):
        self.base.add_insumo("Harina", "kg", 1100.0, 2.0)
        self.reabrir()
        self.assertEqual([i["nombre"] for i in self.base.get_insumos()], ["Harina"])
        self.assertEqual(self.base.version_esquema(), db.VERSION_ESQUEMA)

    def test_unidad_se_guarda_sin_reinterpretar(self):
        for unidad in ("10kg", "10 kg", "12", "kg", "un", "lt", "porción"):
            self.base.add_insumo(f"x {unidad}", unidad, 1.0, 0.0)
        self.assertEqual(sorted(i["unidad"] for i in self.base.get_insumos()),
                         sorted(("10kg", "10 kg", "12", "kg", "un", "lt", "porción")))

    def test_esquema_mas_nuevo_no_se_toca(self):
        self.base.cerrar()
        con = sqlite3.connect(self.ruta)
        con.execute(f"PRAGMA user_version = {db.VERSION_ESQUEMA + 1}")
        con.commit()
        con.close()
        with self.assertRaises(db.EsquemaMasNuevo):
            db.BaseLocal(self.ruta)
        self.base = db.BaseLocal.__new__(db.BaseLocal)
        self.base._con = sqlite3.connect(":memory:")  # para que tearDown pueda cerrar algo

    def test_borrado_logico_conserva_la_fila(self):
        i = self.base.add_insumo("Leche", "lt", 1000.0, 0.0)
        self.base.delete_insumo(i)
        self.assertEqual(self.base.get_insumos(), [])
        fila = self.base._con.execute("SELECT deleted_at, version FROM insumos WHERE id = ?", (i,)).fetchone()
        self.assertIsNotNone(fila["deleted_at"])
        self.assertEqual(fila["version"], 2)

    def test_eliminado_no_se_edita_ni_se_usa(self):
        i = self.base.add_insumo("Leche", "lt", 1000.0, 0.0)
        p = self.base.add_plato("Flan", 2500.0, 200.0)
        self.base.delete_insumo(i)
        self.base.update_insumo(i, "Leche entera", "lt", 1100.0, 0.0)
        self.assertIsNone(self.base.add_insumo_a_plato(p, i, 0.5))
        self.assertEqual(self.base.resumen_cola()["pendiente"], 3)  # crear, crear, eliminar


class TestColaSincronizacion(BaseTemporal):
    def test_cada_cambio_genera_una_operacion_en_orden(self):
        i = self.base.add_insumo("Azúcar", "kg", 1000.0, 0.0)
        p = self.base.add_plato("Queque", 5000.0, 800.0)
        r = self.base.add_insumo_a_plato(p, i, 0.3)
        self.base.update_insumo(i, "Azúcar rubia", "kg", 1200.0, 0.0)
        self.base.quitar_insumo_de_plato(r)
        ops = self.base.operaciones_pendientes()
        self.assertEqual([(o["tabla"], o["operacion"]) for o in ops], [
            ("insumos", "crear"), ("platos", "crear"), ("plato_insumos", "crear"),
            ("insumos", "actualizar"), ("plato_insumos", "eliminar"),
        ])
        self.assertEqual(len({o["op_uuid"] for o in ops}), 5)
        # El ingrediente viaja con los UUID de su plato y su insumo, no con ids locales
        rel = ops[2]["datos"]
        self.assertEqual(rel["plato_uuid"], ops[1]["registro_uuid"])
        self.assertEqual(rel["insumo_uuid"], ops[0]["registro_uuid"])
        self.assertNotIn("plato_id", rel)
        self.assertEqual(ops[3]["datos"]["version"], 2)

    def test_cambio_y_operacion_son_atomicos(self):
        # Si falla el INSERT en la cola, el cambio tampoco debe quedar guardado
        original = self.base._encolar

        def falla(*args):
            raise sqlite3.OperationalError("disco lleno (simulado)")

        self.base._encolar = falla
        with self.assertRaises(sqlite3.OperationalError):
            self.base.add_insumo("Huevo", "un", 200.0, 0.0)
        self.base._encolar = original
        self.assertEqual(self.base.get_insumos(), [])
        self.assertEqual(sum(self.base.resumen_cola().values()), 0)

    def test_estados_e_intentos(self):
        self.base.add_insumo("Sal", "kg", 800.0, 0.0)
        op = self.base.operaciones_pendientes()[0]["op_uuid"]
        self.base.marcar_operacion(op, "en_proceso")
        self.assertEqual(self.base.operaciones_pendientes(), [])
        self.base.marcar_operacion(op, "error", "sin conexión")
        pend = self.base.operaciones_pendientes()
        self.assertEqual((pend[0]["intentos"], pend[0]["ultimo_error"]), (1, "sin conexión"))
        self.base.marcar_operacion(op, "sincronizada")
        self.assertEqual(self.base.resumen_cola()["sincronizada"], 1)
        with self.assertRaises(ValueError):
            self.base.marcar_operacion(op, "inventado")
        with self.assertRaises(KeyError):
            self.base.marcar_operacion("no-existe", "pendiente")

    def test_cierre_durante_sincronizacion_se_recupera(self):
        self.base.add_insumo("Pimienta", "kg", 9000.0, 0.0)
        op = self.base.operaciones_pendientes()[0]["op_uuid"]
        self.base.marcar_operacion(op, "en_proceso")
        self.reabrir()  # simula que la app se cerró en medio del envío
        self.assertEqual([o["op_uuid"] for o in self.base.operaciones_pendientes()], [op])

    def test_la_cola_sobrevive_al_reabrir(self):
        self.base.add_plato("Sopa", 3000.0, 400.0)
        self.reabrir()
        self.assertEqual(self.base.resumen_cola()["pendiente"], 1)


if __name__ == "__main__":
    unittest.main()
