"""Inventario en SQLite. Mismos casos y valores esperados que supabase/tests/database/inventario.test.sql,
para comprobar que el teléfono calcula igual que el servidor.

Ejecutar desde la raíz: python -m unittest discover -s tests -v
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db  # noqa: E402
from services import inventario as inv  # noqa: E402

AHORA = datetime.now(timezone.utc)


class BaseInventario(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self._tmp.name, db.NOMBRE_ARCHIVO)
        self.base = db.BaseLocal(self.ruta)
        self.harina = self.base.add_insumo("Harina", "25kg", 0, 0.1)   # merma 10 % (fracción, como la app)
        self.base.set_unidad_base(self.harina, "g")

    def tearDown(self):
        self.base.cerrar()
        self._tmp.cleanup()

    def inv(self, insumo=None):
        return self.base.inventario(insumo or self.harina)


class TestCasoDelSaco(BaseInventario):
    def test_dos_compras_a_distinto_precio_con_consumo_intermedio(self):
        self.assertEqual(self.base.registrar_compra(self.harina, 25, "kg", 25000), D("1.000000"))
        self.assertEqual((self.inv()["stock_actual"], self.inv()["costo_promedio"]), (D("25000"), D("1.000000")))

        consumo = self.base.registrar_consumo(self.harina, 10, "kg")
        self.assertEqual((consumo.costo_total, consumo.stock_negativo), (D("10000.000000"), False))
        self.assertEqual(self.inv()["stock_actual"], D("15000"))

        self.assertEqual(self.base.registrar_compra(self.harina, 25000, "g", 30000), D("1.200000"))
        i = self.inv()
        self.assertEqual(i["stock_actual"], D("40000"))
        self.assertEqual(i["costo_promedio"], D("1.125000"), "(15.000×1,0 + 30.000) / 40.000")
        self.assertEqual(i["costo_reposicion"], D("1.200000"), "la cotización usa el precio nuevo")

    def test_el_inventario_no_sube_la_version_del_insumo(self):
        self.base.registrar_compra(self.harina, 25, "kg", 25000)
        self.base.registrar_consumo(self.harina, 1, "kg")
        version = self.base._con.execute("SELECT version FROM insumos WHERE id = ?", (self.harina,)).fetchone()[0]
        self.assertEqual(version, 2, "solo set_unidad_base subió la versión")


class TestReglasIgualesAlServidor(BaseInventario):
    def setUp(self):
        super().setUp()
        self.base.registrar_compra(self.harina, 25000, "g", 25000)
        self.base.registrar_consumo(self.harina, 10000, "g")
        self.base.registrar_compra(self.harina, 25000, "g", 30000)

    def test_stock_negativo_con_aviso_y_compra_posterior(self):
        r = self.base.registrar_consumo(self.harina, 45000, "g")
        self.assertTrue(r.stock_negativo)
        self.assertEqual(r.costo_total, D("50625.000000"))
        self.assertEqual(self.inv()["stock_actual"], D("-5000"))
        self.assertTrue(self.inv()["stock_negativo"])
        self.base.registrar_compra(self.harina, 10000, "g", 13000)
        self.assertEqual((self.inv()["stock_actual"], self.inv()["costo_promedio"]), (D("5000"), D("1.300000")))

    def test_compra_antigua_registrada_tarde(self):
        self.base.registrar_consumo(self.harina, 45000, "g")
        self.base.registrar_compra(self.harina, 10000, "g", 13000)
        self.base.registrar_compra(self.harina, 1000, "g", 900, comprada_en=AHORA - timedelta(days=10))
        self.assertEqual(self.inv()["costo_promedio"], D("1.233333"))
        self.assertEqual(self.inv()["costo_reposicion"], D("1.300000"))

    def test_precio_de_mercado(self):
        self.base.actualizar_costo_reposicion(self.harina, "1.5")
        self.assertEqual(self.inv()["costo_reposicion"], D("1.500000"))
        self.assertEqual(self.inv()["costo_promedio"], D("1.125000"), "no toca el promedio")
        self.base.actualizar_costo_reposicion(self.harina, "1.4", AHORA - timedelta(days=5))
        self.assertEqual(self.inv()["costo_reposicion"], D("1.500000"), "un dato más antiguo no reemplaza")

    def test_alerta_de_30_dias(self):
        aceite = self.base.add_insumo("Aceite", "lt", 0, 0)
        self.base.set_unidad_base(aceite, "ml")
        self.base.actualizar_costo_reposicion(aceite, "3.5", AHORA - timedelta(days=31))
        self.assertTrue(self.inv(aceite)["costo_desactualizado"])
        self.assertFalse(self.inv()["costo_desactualizado"])

    def test_produccion_con_merma_en_porcentaje(self):
        pan = self.base.add_plato("Pan amasado", 1500, 0)
        self.base.add_insumo_a_plato(pan, self.harina, 0.2, "kg")
        # 3 × 0,2 kg × 1000 × 1,10 = 660 g al promedio 1,125 = 742,5
        self.assertEqual(self.base.registrar_produccion(pan, 3), D("742.500000"))
        self.assertEqual(self.inv()["stock_actual"], D("39340"))

    def test_produccion_no_convierte_masa_en_volumen(self):
        aceite = self.base.add_insumo("Aceite", "lt", 0, 0)
        self.base.set_unidad_base(aceite, "ml")
        mayo = self.base.add_plato("Mayonesa", 900, 0)
        self.base.add_insumo_a_plato(mayo, aceite, 50, "g")
        with self.assertRaises(inv.ErrorInventario):
            self.base.registrar_produccion(mayo, 1)
        self.assertEqual(self.inv(aceite)["stock_actual"], D("0"), "nada a medias")

    def test_produccion_con_ingrediente_sin_unidad(self):
        plato = self.base.add_plato("Antiguo", 900, 0)
        self.base.add_insumo_a_plato(plato, self.harina, 0.2)        # unidad antigua, sin confirmar
        with self.assertRaises(inv.ErrorInventario):
            self.base.registrar_produccion(plato, 1)

    def test_costo_proyectado_con_reposicion(self):
        plato = self.base.add_plato("Pan", 1500, 100)
        self.base.add_insumo_a_plato(plato, self.harina, 0.2, "kg")
        r = self.base.costo_proyectado(plato)
        self.assertEqual(r.costo, D("364.00"), "200 g × 1,2 × 1,10 + 100")
        self.assertTrue(r.completo)


class TestValidaciones(BaseInventario):
    def test_insumo_sin_unidad_base_no_lleva_inventario(self):
        comino = self.base.add_insumo("Comino", "10kg", 0, 0)
        with self.assertRaises(inv.ErrorInventario):
            self.base.registrar_compra(comino, 1, "kg", 500)
        with self.assertRaises(inv.ErrorInventario):
            self.base.registrar_consumo(comino, 1, "kg")

    def test_unidad_base_no_se_cambia(self):
        with self.assertRaises(inv.ErrorInventario):
            self.base.set_unidad_base(self.harina, "ml")
        with self.assertRaises(inv.ErrorInventario):
            self.base.set_unidad_base(self.base.add_insumo("X", "", 0, 0), "kg")   # kg no es base

    def test_rechazos(self):
        for args in ((0, "g", 100), (1, "g", -1), (1, "ml", 100), (1, "10kg", 100)):
            with self.assertRaises(inv.ErrorInventario, msg=args):
                self.base.registrar_compra(self.harina, *args)
        with self.assertRaises(inv.ErrorInventario):
            self.base.registrar_compra(self.harina, 1, "g", 1, comprada_en=AHORA + timedelta(days=3))
        with self.assertRaises(inv.ErrorInventario):
            self.base.registrar_consumo(self.harina, 1, "g", motivo="produccion")
        self.assertEqual(self.inv()["stock_actual"], D("0"))

    def test_consumo_sin_compras_no_inventa_costo(self):
        r = self.base.registrar_consumo(self.harina, 100, "g")
        self.assertEqual((r.costo_unitario, r.costo_total, r.stock_negativo), (None, None, True))


class TestColaYProvisional(BaseInventario):
    def test_movimientos_van_a_la_cola_en_orden(self):
        self.base.registrar_compra(self.harina, 25, "kg", 25000)
        self.base.registrar_consumo(self.harina, 1, "kg")
        self.base.actualizar_costo_reposicion(self.harina, 2)
        ops = [(o["tabla"], o["operacion"]) for o in self.base.operaciones_pendientes()]
        self.assertEqual(ops[-3:], [("compras_insumos", "crear"), ("consumos_insumos", "crear"),
                                    ("costos_reposicion", "actualizar")])
        compra = self.base.operaciones_pendientes()[-3]["datos"]
        self.assertEqual(compra["cantidad_comprada"], "25000", "en unidad base y como texto exacto")
        self.assertIn("insumo_uuid", compra)

    def test_la_cola_no_lleva_columnas_del_servidor(self):
        self.base.registrar_compra(self.harina, 25, "kg", 25000)
        self.base.update_insumo(self.harina, "Harina flor", "25kg", 0, 0.1)
        datos = self.base.operaciones_pendientes()[-1]["datos"]
        for columna in ("stock_actual", "costo_promedio", "costo_reposicion", "costo_actualizado_en"):
            self.assertNotIn(columna, datos)

    def test_provisional_hasta_que_el_servidor_confirma(self):
        self.assertFalse(self.inv()["provisional"])
        self.base.registrar_compra(self.harina, 25, "kg", 25000)
        self.assertTrue(self.inv()["provisional"])
        for op in self.base.operaciones_pendientes():
            self.base.marcar_operacion(op["op_uuid"], "sincronizada")
        self.assertFalse(self.inv()["provisional"])

    def test_produccion_es_una_sola_operacion(self):
        pan = self.base.add_plato("Pan", 1500, 0)
        self.base.add_insumo_a_plato(pan, self.harina, 0.2, "kg")
        self.base.registrar_compra(self.harina, 25, "kg", 25000)
        antes = len(self.base.operaciones_pendientes())
        self.base.registrar_produccion(pan, 2)
        nuevas = self.base.operaciones_pendientes()[antes:]
        self.assertEqual([(o["tabla"], o["datos"]["porciones"]) for o in nuevas], [("producciones", "2")])

    def test_todo_sobrevive_al_reabrir(self):
        self.base.registrar_compra(self.harina, 25, "kg", 25000)
        self.base.cerrar()
        self.base = db.BaseLocal(self.ruta)
        self.assertEqual(self.inv()["stock_actual"], D("25000"))
        self.assertTrue(self.inv()["provisional"])


class TestMigracionDeEsquema(unittest.TestCase):
    def test_una_base_v1_pasa_a_v2_sin_perder_datos(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, db.NOMBRE_ARCHIVO)
            con = sqlite3.connect(ruta)
            for sentencia in db._MIGRACIONES[0].split(";"):
                if sentencia.strip():
                    con.execute(sentencia)
            con.execute("INSERT INTO insumos (uuid, nombre, unidad, precio, merma_pct, fecha_creacion, updated_at)"
                        " VALUES ('u-1', 'Tomate', 'kg', 1200, 5, '2026-01-01 10:00:00', 'x')")
            con.execute("PRAGMA user_version = 1")
            con.commit()
            con.close()
            base = db.BaseLocal(ruta)
            try:
                self.assertEqual(base.version_esquema(), 2)
                self.assertEqual([(i["nombre"], i["precio"]) for i in base.get_insumos()], [("Tomate", 1200.0)])
                i = base.inventario(1)
                self.assertEqual((i["unidad_base"], i["stock_actual"]), (None, D("0")),
                                 "los insumos antiguos quedan sin inventario hasta confirmar su unidad")
            finally:
                base.cerrar()


if __name__ == "__main__":
    unittest.main()
