"""Pruebas del costo proyectado. Ejecutar desde la raíz: python -m unittest discover -s tests -v"""
import os
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from services import calculo_costos as cc  # noqa: E402

AHORA = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)


def harina(**cambios):
    """Harina tras el caso del saco: promedio 1,125 $/g y reposición 1,2 $/g."""
    base = {"nombre": "Harina", "cantidad": "0.2", "unidad": "kg", "unidad_base": "g",
            "costo_reposicion": "1.2", "merma_pct": "0.1", "costo_actualizado_en": AHORA - timedelta(days=2),
            "stock_actual": "35000"}
    base.update(cambios)
    return base


class TestCostoProyectado(unittest.TestCase):
    def test_cotiza_con_el_costo_de_reposicion(self):
        # 0,2 kg = 200 g × 1,2 $/g × 1,10 (merma 10 %) = 264 ; + mano de obra 100
        r = cc.costo_proyectado_plato([harina()], costo_mano_obra=100, ahora=AHORA)
        self.assertEqual(r.costo, Decimal("364.00"))
        self.assertTrue(r.completo)
        self.assertEqual((r.desactualizados, r.stock_negativo), ([], []))

    def test_el_promedio_contable_daria_menos_margen_protegido(self):
        # Con el promedio (1,125) la cotización sería 247,50: subestima el alza del proveedor
        con_promedio = cc.costo_proyectado_plato([harina(costo_reposicion="1.125")], ahora=AHORA)
        con_reposicion = cc.costo_proyectado_plato([harina()], ahora=AHORA)
        self.assertEqual(con_promedio.costo, Decimal("247.50"))
        self.assertGreater(con_reposicion.costo, con_promedio.costo)

    def test_conversion_dentro_de_la_misma_dimension(self):
        mismo_en_gramos = cc.costo_proyectado_plato([harina(cantidad=200, unidad="g")], ahora=AHORA)
        self.assertEqual(mismo_en_gramos.costo, Decimal("264.00"))
        huevos = {"nombre": "Huevo", "cantidad": 1, "unidad": "docena", "unidad_base": "unidad",
                  "costo_reposicion": 180, "merma_pct": 0}
        self.assertEqual(cc.costo_proyectado_plato([huevos]).costo, Decimal("2160.00"))

    def test_no_convierte_masa_en_volumen(self):
        aceite = {"nombre": "Aceite", "cantidad": 50, "unidad": "g", "unidad_base": "ml",
                  "costo_reposicion": "3.5", "merma_pct": 0}
        r = cc.costo_proyectado_plato([harina(), aceite], ahora=AHORA)
        self.assertFalse(r.completo)
        self.assertEqual(r.unidad_incompatible, ["Aceite"])
        self.assertEqual(r.costo, Decimal("264.00"))   # solo lo calculable, marcado incompleto

    def test_unidad_antigua_sin_confirmar_no_se_interpreta(self):
        r = cc.costo_proyectado_plato([harina(unidad="10kg"), harina(nombre="Sal", unidad=None)], ahora=AHORA)
        self.assertEqual(r.unidad_incompatible, ["Harina", "Sal"])
        self.assertEqual(r.costo, Decimal("0.00"))

    def test_sin_costo_de_reposicion(self):
        r = cc.costo_proyectado_plato([harina(costo_reposicion=None)], ahora=AHORA)
        self.assertEqual((r.sin_costo, r.completo), (["Harina"], False))

    def test_alerta_de_30_dias(self):
        viejo = cc.costo_proyectado_plato([harina(costo_actualizado_en=AHORA - timedelta(days=31))], ahora=AHORA)
        al_limite = cc.costo_proyectado_plato([harina(costo_actualizado_en=AHORA - timedelta(days=30))], ahora=AHORA)
        self.assertEqual(viejo.desactualizados, ["Harina"])
        self.assertEqual(al_limite.desactualizados, [])
        self.assertTrue(viejo.completo, "la alerta avisa, no impide cotizar")

    def test_aviso_de_stock_negativo(self):
        r = cc.costo_proyectado_plato([harina(stock_actual="-5000")], ahora=AHORA)
        self.assertEqual(r.stock_negativo, ["Harina"])

    def test_decimal_sin_errores_de_float(self):
        # Con float, 0.1 × 3 × 0.7 arrastra decimales binarios; con Decimal es exacto
        sal = {"nombre": "Sal", "cantidad": 0.1, "unidad": "kg", "unidad_base": "g",
               "costo_reposicion": 0.7, "merma_pct": 0}
        self.assertEqual(cc.costo_proyectado_plato([sal, sal, sal]).costo, Decimal("210.00"))


class TestFormulaActualIntacta(unittest.TestCase):
    """D5: la fórmula de hoy no cambia; el informe muestra la diferencia."""

    def test_costo_real_plato_sigue_igual(self):
        self.assertEqual(cc.costo_real_plato([{"cantidad": 0.2, "precio": 1000, "merma_pct": 0.1}], 50), 270.0)

    def test_mismo_precio_y_merma_dan_el_mismo_costo(self):
        # Ambas fórmulas usan la merma como fracción (0,1 = 10 %): con el mismo precio
        # coinciden, y la diferencia solo viene del cambio de precio (reposición).
        actual = [{"cantidad": 0.2, "precio": 1000, "merma_pct": 0.1}]
        igual = [{"nombre": "Harina", "cantidad": 0.2, "unidad": "kg", "unidad_base": "g",
                  "costo_reposicion": 1, "merma_pct": 0.1}]
        c = cc.comparar_formulas(actual, igual, 50)
        self.assertEqual((c["actual"], c["proyectado"], c["diferencia"]), (Decimal("270.0"), Decimal("270.00"), 0))
        subio = [dict(igual[0], costo_reposicion="1.2")]
        self.assertEqual(cc.comparar_formulas(actual, subio, 50)["diferencia"], Decimal("44.00"))


class TestCatalogoIgualAlDeSQL(unittest.TestCase):
    def test_unidades_coinciden_con_la_migracion(self):
        ruta = os.path.join(RAIZ, "supabase", "migrations", "20261126000000_esquema_inicial.sql")
        with open(ruta, encoding="utf-8") as f:
            sql = f.read()
        bloque = sql.split("insert into public.unidades", 1)[1].split(";", 1)[0]
        filas = re.findall(r"\('(\w+)',\s*'[^']*',\s*'(\w+)',\s*'(\w+)',\s*([\d.]+)\)", bloque)
        en_sql = {c: (d, b, Decimal(f)) for c, d, b, f in filas}
        self.assertEqual(en_sql, cc.UNIDADES)


if __name__ == "__main__":
    unittest.main()
