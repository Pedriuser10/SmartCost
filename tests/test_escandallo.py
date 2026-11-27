"""Pruebas de services/escandallo.py. Solo carpetas temporales."""
import os
import sys
import tempfile
import unittest
from decimal import Decimal as D

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import confirmaciones as conf, rutas, storage  # noqa: E402
from services import escandallo  # noqa: E402
from services.calculo_costos import costo_real_plato, margen  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        rutas.configurar(self._tmp.name)
        os.makedirs(rutas.datos_dir())
        for args in (("Carne molida", "kg", 6500, 0.05), ("Pan hamburguesa", "un", 350, 0.02),
                     ("Pescado", "8kg", 120000, 0), ("Huevos", "12", 4200, 0)):
            storage.add_insumo(*args)
        self.ins = {i["nombre"]: i for i in storage.get_insumos()}
        self.burger = storage.add_plato("Hamburguesa", 4500, 800)
        storage.add_insumo_a_plato(self.burger, self.ins["Carne molida"]["id"], 0.15)
        storage.add_insumo_a_plato(self.burger, self.ins["Pan hamburguesa"]["id"], 1)
        self.ceviche = storage.add_plato("Ceviche", 12000, 4990)
        storage.add_insumo_a_plato(self.ceviche, self.ins["Pescado"]["id"], 1)
        storage.add_insumo_a_plato(self.ceviche, self.ins["Huevos"]["id"], 1)

    def tearDown(self):
        self._tmp.cleanup()


class TestEscandallo(Base):
    def test_sin_confirmar_y_formula_actual_es_igual_a_la_formula_historica(self):
        for pid in (self.burger, self.ceviche):
            plato = storage.get_plato(pid)
            e = escandallo.calcular(plato)
            historico = costo_real_plato(storage.get_insumos_de_plato(pid), plato["mano_obra"])
            self.assertAlmostEqual(float(e.costo), historico, places=2)
            self.assertAlmostEqual(float(e.margen), margen(plato["precio_venta"], historico), places=2)

    def test_formula_propuesta_al_lado(self):
        e = escandallo.calcular(storage.get_plato(self.burger))
        # actual: 0,15×6.500×1,05 + 350×1,02 + 800 ; propuesta: 975/0,95 + 350/0,98 + 800
        self.assertEqual(e.costo.quantize(D("0.01")), D("2180.75"))
        self.assertEqual(e.costo_otra_formula.quantize(D("0.01")), D("2183.46"))
        p = escandallo.calcular(storage.get_plato(self.burger), formula="propuesta")
        self.assertEqual(p.costo.quantize(D("0.01")), D("2183.46"))

    def test_paquete_sin_confirmar_avisa_y_no_se_reinterpreta(self):
        e = escandallo.calcular(storage.get_plato(self.ceviche))
        pescado, huevos = e.filas
        self.assertEqual(pescado.subtotal, D("120000"))
        self.assertIn("8 kg", pescado.aviso)
        self.assertEqual(pescado.si_confirma, D("15000"))
        self.assertIn("«12»", huevos.aviso)
        self.assertIsNone(huevos.si_confirma)
        self.assertEqual(e.avisos, 2)

    def test_paquete_confirmado_se_divide(self):
        conf.confirmar(self.ins["Pescado"], "g", 8, "kg", "kg")
        conf.confirmar(self.ins["Huevos"], "unidad", 12, "unidad", "unidad")
        e = escandallo.calcular(storage.get_plato(self.ceviche))
        pescado, huevos = e.filas
        self.assertEqual((pescado.subtotal, pescado.confirmado, pescado.aviso), (D("15000"), True, ""))
        self.assertEqual(huevos.subtotal, D("350"))
        self.assertEqual(e.costo, D("15000") + D("350") + D("4990"))

    def test_simulacion_porciones_cantidades_y_precio(self):
        plato = storage.get_plato(self.burger)
        rel_carne = storage.get_insumos_de_plato(self.burger)[0]["rel_id"]
        e = escandallo.calcular(plato, porciones=5, cantidades={rel_carne: 0.2}, mano_obra=1000, precio=5000)
        self.assertEqual(e.filas[0].cantidad, D("0.2"))
        self.assertEqual(e.mano_obra, D("5000"))
        self.assertEqual(e.precio, D("25000"))
        self.assertEqual(e.costo, (D("0.2") * 6500 * D("1.05") + 350 * D("1.02")) * 5 + 5000)
        self.assertEqual(storage.get_insumos_de_plato(self.burger)[0]["cantidad"], 0.15, "la simulación no guarda")

    def test_resumen_ordenado_por_margen(self):
        res = escandallo.resumen_platos()
        self.assertEqual([p["nombre"] for p, _ in res], ["Hamburguesa", "Ceviche"])
        self.assertGreater(res[0][1].margen, res[1][1].margen)

    def test_precio_cero_y_formula_invalida(self):
        e = escandallo.calcular(storage.get_plato(self.burger), precio=0)
        self.assertEqual(e.margen, 0)
        with self.assertRaises(ValueError):
            escandallo.calcular(storage.get_plato(self.burger), formula="otra")


if __name__ == "__main__":
    unittest.main()
