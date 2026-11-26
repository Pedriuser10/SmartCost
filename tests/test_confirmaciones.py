"""Pruebas de models/confirmaciones.py. Solo carpetas temporales; nunca datos reales."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from decimal import Decimal as D

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import confirmaciones as conf, rutas, storage  # noqa: E402


def _sha(ruta):
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class TestSugerencias(unittest.TestCase):
    def test_textos_con_envase_y_sin_envase(self):
        casos = {
            "10kg": ("g", D("10"), "kg", "kg"), "10 kg": ("g", D("10"), "kg", "kg"),
            "5kg": ("g", D("5"), "kg", "kg"), "kg": ("g", D("1"), "kg", "kg"),
            "lt": ("ml", D("1"), "l", "l"), "un": ("unidad", D("1"), "unidad", "unidad"),
            "2,5 kg": ("g", D("2.5"), "kg", "kg"),
        }
        for texto, esperado in casos.items():
            s = conf.sugerir(texto)
            self.assertEqual((s.unidad_base, s.contenido, s.unidad_contenido, s.unidad_receta), esperado, texto)

    def test_sin_sugerencia_cuando_no_es_seguro(self):
        for texto in ("12", "porción", "cc", "", None, "0 kg", "taza"):
            self.assertIsNone(conf.sugerir(texto), texto)


class TestInterpretacion(unittest.TestCase):
    SACO = {"id": 1, "nombre": "Harina", "unidad": "10kg", "precio": 5000, "merma_pct": 0.1}

    def test_costo_por_unidad_base(self):
        # $5.000 por un envase de 10 kg → $0,5 por gramo (ejemplo de D5)
        self.assertEqual(conf.interpretar(self.SACO, "g", 10, "kg", "kg"), D("0.5"))
        self.assertEqual(conf.interpretar(self.SACO, "g", "1", "kg", "g"), D("5"))

    def test_rechaza_dimensiones_distintas_y_valores_invalidos(self):
        for args in (("ml", 10, "kg", "kg"), ("g", 10, "kg", "l"), ("kg", 10, "kg", "kg"),
                     ("g", 0, "kg", "kg"), ("g", "abc", "kg", "kg"), ("g", 10, "taza", "kg")):
            with self.assertRaises(conf.ErrorConfirmacion, msg=args):
                conf.interpretar(self.SACO, *args)

    def test_impacto_muestra_hoy_y_con_la_interpretacion(self):
        # Receta con 0,15 (kg). Hoy: 0,15 × 5.000 × 1,1 = 825 (usa el precio del saco como si fuera por kg)
        # Interpretado como saco de 10 kg: 0,15 kg = 150 g × 0,5 × 1,1 = 82,50
        costo, filas = conf.impacto(self.SACO, [("Pan", 0.15)], "g", 10, "kg", "kg")
        self.assertEqual(costo, D("0.5"))
        self.assertEqual((filas[0].costo_hoy, filas[0].costo_interpretado), (D("825.00"), D("82.50")))
        # Si en realidad el precio es por kg, ambos coinciden
        _, filas = conf.impacto(self.SACO, [("Pan", 0.15)], "g", 1, "kg", "kg")
        self.assertEqual(filas[0].costo_hoy, filas[0].costo_interpretado)


class TestArchivo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        rutas.configurar(self._tmp.name)
        os.makedirs(rutas.datos_dir())
        storage.add_insumo("Harina", "10kg", 5000.0, 0.1)
        storage.add_insumo("Huevos", "12", 2400.0, 0.0)
        self.harina, self.huevos = sorted(storage.get_insumos(), key=lambda i: i["id"])

    def tearDown(self):
        self._tmp.cleanup()

    def test_confirmar_no_modifica_app_json(self):
        antes = _sha(rutas.archivo_app())
        conf.confirmar(self.harina, "g", 10, "kg", "kg")
        self.assertEqual(_sha(rutas.archivo_app()), antes)
        with open(conf.archivo(), encoding="utf-8") as f:
            guardado = json.load(f)["confirmaciones"]["1"]
        self.assertEqual((guardado["unidad_base"], guardado["contenido"], guardado["costo_por_unidad_base"]),
                         ("g", "10", "0.5"))
        self.assertEqual(guardado["sha256_app_json"], antes)
        self.assertFalse(os.path.exists(conf.archivo() + ".tmp"))

    def test_estados_y_resumen(self):
        self.assertEqual(conf.estado(self.harina), conf.PENDIENTE)
        conf.confirmar(self.harina, "g", 10, "kg", "kg")
        self.assertEqual(conf.estado(self.harina), conf.CONFIRMADO)
        self.assertEqual(conf.resumen(storage.get_insumos()),
                         {conf.PENDIENTE: 1, conf.CONFIRMADO: 1, conf.REVISAR: 0})

    def test_cambiar_nombre_o_unidad_obliga_a_revisar(self):
        conf.confirmar(self.harina, "g", 10, "kg", "kg")
        storage.update_insumo(self.harina["id"], "Harina", "25kg", 5000.0, 0.1)
        cambiado = next(i for i in storage.get_insumos() if i["id"] == self.harina["id"])
        self.assertEqual(conf.estado(cambiado), conf.REVISAR)
        self.assertIsNone(conf.confirmacion(cambiado), "una confirmación por revisar no se usa")

    def test_cambiar_precio_o_merma_no_la_invalida(self):
        conf.confirmar(self.harina, "g", 10, "kg", "kg")
        storage.update_insumo(self.harina["id"], "Harina", "10kg", 6000.0, 0.05)
        cambiado = next(i for i in storage.get_insumos() if i["id"] == self.harina["id"])
        self.assertEqual(conf.estado(cambiado), conf.CONFIRMADO)

    def test_un_error_no_guarda_nada(self):
        with self.assertRaises(conf.ErrorConfirmacion):
            conf.confirmar(self.huevos, "unidad", 12, "kg", "unidad")
        self.assertFalse(os.path.exists(conf.archivo()))

    def test_quitar(self):
        conf.confirmar(self.huevos, "unidad", 12, "unidad", "unidad")
        conf.quitar(self.huevos["id"])
        self.assertEqual(conf.estado(self.huevos), conf.PENDIENTE)

    def test_formato_desconocido_no_se_sobrescribe(self):
        with open(conf.archivo(), "w", encoding="utf-8") as f:
            json.dump({"version": 99}, f)
        with self.assertRaises(conf.ErrorConfirmacion):
            conf.confirmar(self.harina, "g", 10, "kg", "kg")
        with open(conf.archivo(), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"version": 99})


if __name__ == "__main__":
    unittest.main()
