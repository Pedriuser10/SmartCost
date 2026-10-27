"""Pantalla 'Ingeniería de Menú': ranking de rentabilidad de todos los platos."""
import os
from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDButton, MDButtonText
from models import storage
from services.calculo_costos import costo_real_plato, margen, COLOR_MARGEN, clasificar_margen
import uuid
import matplotlib.pyplot as plt
from kivymd.uix.fitimage import FitImage
from models.storage import IMAGENES_DIR
from kivy.uix.image import Image


class IngenieriaMenuScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="ingenieria_de_menu", md_bg_color=(0.95, 0.95, 0.95, 1), **kwargs)
        root = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(16))
        back = MDButton(MDButtonText(text="‹  Volver al inicio"), style="text", size_hint_y=None, height=dp(48))
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "inicio"))
        root.add_widget(back)
        root.add_widget(MDLabel(text="Ingeniería de Menú", font_style="Headline", role="medium", bold=True, size_hint_y=None, height=dp(52), theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1)))
        self.resumen_label = MDLabel(text="", theme_text_color="Secondary", size_hint_y=None, height=dp(30))
        root.add_widget(self.resumen_label)
        scroll = MDScrollView()
        self.container = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        self.container.bind(minimum_height=self.container.setter("height"))
        scroll.add_widget(self.container)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_pre_enter(self, *args):
        self.refrescar()

    def refrescar(self):
        self.container.clear_widgets()
        resultados = []
        for plato in storage.get_platos():
            usados = storage.get_insumos_de_plato(plato["id"])
            costo = costo_real_plato(usados, plato["mano_obra"])
            m = margen(plato["precio_venta"], costo)
            resultados.append({"nombre": plato["nombre"], "precio_venta": plato["precio_venta"], "costo": costo, "margen": m, "categoria": clasificar_margen(m)})

        resultados.sort(key=lambda r: r["margen"], reverse=True)

        if resultados:
            promedio = sum(r["margen"] for r in resultados) / len(resultados)
            self.resumen_label.text = f"Margen promedio del menú: {promedio:.1f}%"
            nombres = [r["nombre"] for r in resultados]
            margenes = [r["margen"] for r in resultados]

            plt.figure(figsize=(6, 3))
            plt.bar(nombres, margenes, color='#4CAF50')
            plt.title("Rentabilidad por Plato (%)")
            plt.ylabel("Margen")
            plt.tight_layout()

           
            os.makedirs(IMAGENES_DIR, exist_ok=True)
            nombre_grafico = f"grafico_{uuid.uuid4().hex[:6]}.png" 
            ruta_grafico = os.path.join(IMAGENES_DIR, nombre_grafico)
            plt.savefig(ruta_grafico)
            plt.close()

            
            grafico_card = MDCard(size_hint_y=None, height=dp(260), radius=[dp(10)], padding=dp(8), md_bg_color=(1, 1, 1, 1))
            grafico_card.add_widget(Image(source=ruta_grafico, allow_stretch=True, keep_ratio=True))
            self.container.add_widget(grafico_card)
        else:
            self.resumen_label.text = "Aún no hay platos cargados. Créalos en 'Mis Recetas'."
        for r in resultados:
            card = MDCard(orientation="vertical", size_hint_y=None, height=dp(90), padding=dp(12), spacing=dp(4), theme_bg_color="Custom", md_bg_color=COLOR_MARGEN[r["categoria"]], radius=[dp(10)])
            card.add_widget(MDLabel(text=r["nombre"], bold=True, font_style="Title", role="medium", theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1)))
            card.add_widget(MDLabel(text=f"Venta ${r['precio_venta']:,.0f}  ·  Costo real ${r['costo']:,.0f}  ·  Margen {r['margen']:.1f}%", theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1)))
            self.container.add_widget(card)