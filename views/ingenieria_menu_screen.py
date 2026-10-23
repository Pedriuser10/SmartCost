"""Pantalla 'Ingeniería de Menú': ranking de rentabilidad de todos los platos."""
from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDButton , MDButtonText
from models import storage
from services.calculo_costos import costo_real_plato, margen , COLOR_MARGEN, clasificar_margen


class IngenieriaMenuScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="ingenieria_de_menu", md_bg_color=(0.95, 0.95, 0.95, 1), **kwargs)

        root = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(16))

        back = MDButton(MDButtonText(text="‹  Volver al inicio", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48))
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "inicio"))
        root.add_widget(back)

        root.add_widget(
            MDLabel(text="Ingeniería de Menú", font_style="Headline", role="medium", bold=True, size_hint_y=None, height=dp(52),
                    theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1))
        )

        self.resumen_label = MDLabel(
            text="", theme_text_color="Secondary", size_hint_y=None, height=dp(30)
        )
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
            resultados.append({
                "nombre": plato["nombre"],
                "precio_venta": plato["precio_venta"],
                "costo": costo,
                "margen": m,
                "categoria": clasificar_margen(m),
            })

        resultados.sort(key=lambda r: r["margen"], reverse=True)

        if resultados:
            promedio = sum(r["margen"] for r in resultados) / len(resultados)
            self.resumen_label.text = f"Margen promedio del menú: {promedio:.1f}%"
        else:
            self.resumen_label.text = "Aún no hay platos cargados. Créalos en 'Mis Recetas'."

        for r in resultados:
            card = MDCard(
                orientation="vertical", size_hint_y=None, height=dp(90),
                padding=dp(12), spacing=dp(4),
                md_bg_color=COLOR_MARGEN[r["categoria"]], radius=[dp(10)],
            )
            card.add_widget(MDLabel(
                text=r["nombre"], bold=True, font_style="Title", role="medium",
                theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1),
            ))
            card.add_widget(MDLabel(
                text=f"Venta ${r['precio_venta']:,.0f}  ·  Costo real ${r['costo']:,.0f}  ·  Margen {r['margen']:.1f}%",
                theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1),
            ))
            self.container.add_widget(card)