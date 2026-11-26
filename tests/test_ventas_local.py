"""Venta directa y precio de venta en SQLite. Mismos casos y valores que
supabase/tests/database/ventas.test.sql: el teléfono calcula igual que el servidor.

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


class BaseVentas(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self._tmp.name, db.NOMBRE_ARCHIVO)
        self.base = db.BaseLocal(self.ruta)
        self.jugo = self.base.add_insumo("Jugo en caja", "caja 24", 0, 0)
        self.base.set_unidad_base(self.jugo, "unidad")
        self.base.configurar_venta(self.jugo, True, 30)

    def tearDown(self):
        self.base.cerrar()
        self._tmp.cleanup()

    def p(self, insumo=None):
        return self.base.inventario(insumo or self.jugo)


class TestReglasPuras(unittest.TestCase):
    def test_precio_sugerido_sin_residuos_de_division(self):
        # 500 / 0,7 = 714,2857… : multiplicar primero por el IVA evita que $850 suba a $860
        self.assertEqual(inv.precio_sugerido(500, 30, D("0.19")), D("850"))
        self.assertEqual(inv.precio_sugerido(600, 30, D("0.19")), D("1020"))
        self.assertEqual(inv.precio_sugerido(650, 30, D("0.19")), D("1110"))   # 1.105 → 1.110
        self.assertEqual(inv.precio_sugerido(650, 30, 0), D("930"))            # 928,57 → 930
        self.assertIsNone(inv.precio_sugerido(None, 30, D("0.19")))
        with self.assertRaises(inv.ErrorInventario):
            inv.precio_sugerido(500, 100, D("0.19"))

    def test_margen_real_sobre_el_precio(self):
        self.assertEqual(inv.margen_real(850, 500, D("0.19")), D("30.00"))
        self.assertEqual(inv.margen_real(850, 600, D("0.19")), D("16.00"))
        self.assertIsNone(inv.margen_real(None, 600, D("0.19")))


class TestCasoDelBulto(BaseVentas):
    def test_caja_venta_parcial_y_caja_mas_cara(self):
        self.base.registrar_compra(self.jugo, 24, "unidad", 12000)
        p = self.p()
        self.assertEqual((p["costo_reposicion"], p["precio_sugerido"], p["precio_venta"]), (D("500.000000"), D("850"), None))
        self.assertTrue(p["sin_precio_venta"])
        with self.assertRaises(inv.ErrorInventario):
            self.base.registrar_venta(self.jugo, 1, "unidad")              # sin precio aprobado

        self.assertEqual(self.base.fijar_precio_venta(self.jugo), D("850.00"))
        self.assertEqual((self.p()["margen_real"], self.p()["margen_bajo"]), (D("30.00"), False))

        v = self.base.registrar_venta(self.jugo, 10, "unidad")
        self.assertEqual((v.total, v.ingreso_neto, v.costo_venta, v.utilidad),
                         (D("8500.00"), D("7142.857143"), D("5000.000000"), D("2142.857143")))
        self.assertEqual(self.p()["stock_actual"], D("14"))

        self.base.registrar_compra(self.jugo, 24, "unidad", 14400)
        p = self.p()
        self.assertEqual(p["costo_promedio"], D("563.157895"))
        self.assertEqual((p["costo_reposicion"], p["precio_sugerido"]), (D("600.000000"), D("1020")))
        self.assertEqual(p["precio_venta"], D("850.00"), "el precio de góndola no sube solo")
        self.assertEqual((p["margen_real"], p["margen_bajo"]), (D("16.00"), True))

        self.base.fijar_precio_venta(self.jugo)
        self.assertFalse(self.p()["margen_bajo"])
        self.assertEqual(self.base.registrar_venta(self.jugo, 5, "unidad").costo_venta, D("2815.789475"))
        self.assertEqual(self.base.registrar_venta(self.jugo, 1, "unidad", precio_unitario=900).total, D("900.00"))

    def test_lista_del_proveedor_sin_compra(self):
        self.base.registrar_compra(self.jugo, 24, "unidad", 12000)
        self.base.fijar_precio_venta(self.jugo)
        self.base.actualizar_costo_reposicion(self.jugo, 650)
        p = self.p()
        self.assertEqual((p["precio_sugerido"], p["stock_actual"], p["costo_promedio"]), (D("1110"), D("24"), D("500.000000")))
        self.assertTrue(p["margen_bajo"])


class TestReglas(BaseVentas):
    def test_no_se_vende_lo_que_no_esta_a_la_venta(self):
        harina = self.base.add_insumo("Harina", "25kg", 0, 0)
        self.base.set_unidad_base(harina, "g")
        self.base.registrar_compra(harina, 25, "kg", 20000)
        with self.assertRaises(inv.ErrorInventario):
            self.base.registrar_venta(harina, 1, "kg", precio_unitario=1000)
        with self.assertRaises(inv.ErrorInventario):
            self.base.fijar_precio_venta(harina, 1000)

    def test_venta_con_stock_negativo_tiene_aviso(self):
        self.base.registrar_compra(self.jugo, 24, "unidad", 12000)
        self.base.fijar_precio_venta(self.jugo)
        self.assertTrue(self.base.registrar_venta(self.jugo, 30, "unidad").stock_negativo)

    def test_longitud_en_metros(self):
        cable = self.base.add_insumo("Cable 2,5 mm", "rollo", 0, 0)
        self.base.set_unidad_base(cable, "m")
        self.base.configurar_venta(cable, True, 40)
        self.base.registrar_compra(cable, 100, "m", 50000)
        self.assertEqual(self.p(cable)["precio_sugerido"], D("1000"))   # 991,67 → 1.000
        self.base.fijar_precio_venta(cable)
        self.assertEqual(self.base.registrar_venta(cable, 250, "cm").total, D("2500.00"))   # 2,5 m

    def test_ajustes_iva_y_umbral(self):
        # Sin compras: el único costo es un precio de lista de hace 10 días
        self.base.actualizar_costo_reposicion(self.jugo, 650, AHORA - timedelta(days=10))
        self.assertFalse(self.p()["costo_desactualizado"])
        self.base.set_ajustes(dias_alerta_precio=7)
        self.assertTrue(self.p()["costo_desactualizado"])
        self.base.set_ajustes(tasa_iva=0)
        self.assertEqual(self.p()["precio_sugerido"], D("930"))
        with self.assertRaises(inv.ErrorInventario):
            self.base.set_ajustes(tasa_iva=19)                      # 19 % se escribe 0,19

    def test_margen_invalido(self):
        with self.assertRaises(inv.ErrorInventario):
            self.base.configurar_venta(self.jugo, True, 150)


class TestColaVentas(BaseVentas):
    def test_venta_y_precio_van_a_la_cola_sin_columnas_del_servidor(self):
        self.base.registrar_compra(self.jugo, 24, "unidad", 12000)
        self.base.fijar_precio_venta(self.jugo)
        self.base.registrar_venta(self.jugo, 2, "unidad")
        ops = self.base.operaciones_pendientes()
        self.assertEqual([(o["tabla"], o["operacion"]) for o in ops[-2:]],
                         [("precios_venta", "actualizar"), ("ventas", "crear")])
        self.assertEqual(ops[-1]["datos"]["precio_unitario"], "850.00", "se envía el precio cobrado")
        configurar = next(o for o in ops if o["tabla"] == "insumos" and o["datos"].get("se_vende") == 1)
        for columna in ("precio_venta", "precio_actualizado_en", "stock_actual"):
            self.assertNotIn(columna, configurar["datos"])
        self.assertTrue(self.p()["provisional"])

    def test_aprobar_precio_sube_la_version(self):
        self.base.registrar_compra(self.jugo, 24, "unidad", 12000)
        antes = self.base._con.execute("SELECT version FROM insumos WHERE id = ?", (self.jugo,)).fetchone()[0]
        self.base.fijar_precio_venta(self.jugo)
        despues = self.base._con.execute("SELECT version FROM insumos WHERE id = ?", (self.jugo,)).fetchone()[0]
        self.assertEqual(despues, antes + 1)


class TestMigracionV2aV3(unittest.TestCase):
    def test_una_base_v2_gana_ventas_sin_perder_inventario(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, db.NOMBRE_ARCHIVO)
            con = sqlite3.connect(ruta)
            for migracion in db._MIGRACIONES[:2]:
                for sentencia in migracion.split(";"):
                    if sentencia.strip():
                        con.execute(sentencia)
            con.execute("INSERT INTO insumos (uuid, nombre, unidad, precio, merma_pct, fecha_creacion, updated_at,"
                        " unidad_base, stock_actual) VALUES ('u-1', 'Arroz', 'kg', 1000, 0, 'x', 'x', 'g', '5000')")
            con.execute("PRAGMA user_version = 2")
            con.commit()
            con.close()
            base = db.BaseLocal(ruta)
            try:
                i = base.inventario(1)
                self.assertEqual((base.version_esquema(), i["stock_actual"], i["se_vende"]), (db.VERSION_ESQUEMA, D("5000"), False))
                self.assertEqual((base.tasa_iva(), base.dias_alerta_precio()), (D("0.19"), 30))
            finally:
                base.cerrar()


if __name__ == "__main__":
    unittest.main()
