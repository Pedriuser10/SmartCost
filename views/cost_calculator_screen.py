"""Pantalla 'Calcular Costos': muestra el desglose real de un plato ya cargado en Mis Recetas."""
from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.button import MDButton, MDButtonText
from models import storage
from services.calculo_costos import costo_real_plato, margen


class CostCalculatorScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="calcular_costos", md_bg_color=(0.08, 0.08, 0.1, 1), **kwargs)
        self.menu = None
        self._plato_actual = None

        root = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(16))

        back = MDButton (MDButtonText(text="Volver", size_hint_y=None, height=dp(48), theme_text_color="Custom", text_color=(0.8, 0.8, 0.8, 1)),style="text", size_hint_y=None, height=dp(48))
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "inicio"))
        root.add_widget(back)

        root.add_widget(
            MDLabel(text="Calcular Costos", font_style="Headline", role="medium", bold=True, size_hint_y=None, height=dp(52),
                    theme_text_color="Custom", text_color=(1, 1, 1, 1))
        )
        root.add_widget(
            MDLabel(
                text="Elige un plato de tu carta para ver su costo real calculado a partir de la receta.",
                theme_text_color="Secondary",
                size_hint_y=None, height=dp(40),
            )
        )

        self.selector_btn = MDButton(MDButtonText(text="Elegir plato", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48))
        self.selector_btn.bind(on_release=self._abrir_selector)
        root.add_widget(self.selector_btn)

        scroll = MDScrollView()
        self.resultado_box = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, padding=(0, dp(10)))
        self.resultado_box.bind(minimum_height=self.resultado_box.setter("height"))
        scroll.add_widget(self.resultado_box)
        root.add_widget(scroll)

        self.add_widget(root)

    def on_pre_enter(self, *args):
        if self._plato_actual is None:
            self._mostrar_mensaje_inicial()

    def _mostrar_mensaje_inicial(self):
        self.resultado_box.clear_widgets()
        if not storage.get_platos():
            self.resultado_box.add_widget(
                MDLabel(
                    text="Aún no tienes platos cargados. Ve a 'Mis Recetas' y crea el primero.",
                    theme_text_color="Secondary",
                )
            )

    def _abrir_selector(self, boton):
        platos = storage.get_platos()
        if not platos:
            self._mostrar_mensaje_inicial()
            return
        items = [
            {"text": p["nombre"], "on_release": lambda p=p: self._seleccionar_plato(p)}
            for p in platos
        ]
        self.menu = MDDropdownMenu(caller=boton, items=items, width_mult=4)
        self.menu.open()

    def _seleccionar_plato(self, plato):
        self.menu.dismiss()
        self._plato_actual = plato
        self.selector_btn.text = plato["nombre"]
        self._mostrar_desglose(plato)

    def seleccionar_plato_externo(self, plato):
        """Permite que otra pantalla (ej. Menú Visual) preseleccione un plato al entrar aquí."""
        self._plato_actual = plato
        self.selector_btn.text = plato["nombre"]
        self._mostrar_desglose(plato)

    def _mostrar_desglose(self, plato):
        self.resultado_box.clear_widgets()

        insumos_usados = storage.get_insumos_de_plato(plato["id"])
        if not insumos_usados:
            self.resultado_box.add_widget(
                MDLabel(
                    text=f"'{plato['nombre']}' todavía no tiene insumos asociados. "
                         f"Agrégalos desde Mis Recetas.",
                    theme_text_color="Secondary",
                )
            )
            return

        for item in insumos_usados:
            subtotal = item["cantidad"] * item["precio"] * (1 + item["merma_pct"])
            fila = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30))
            fila.add_widget(MDLabel(
                text=f"{item['nombre']}  ·  {item['cantidad']} {item['unidad']}",
                theme_text_color="Custom", text_color=(0.85, 0.85, 0.85, 1),
            ))
            fila.add_widget(MDLabel(
                text=f"${subtotal:,.0f}", halign="right",
                theme_text_color="Custom", text_color=(0.85, 0.85, 0.85, 1),
            ))
            self.resultado_box.add_widget(fila)

        costo = costo_real_plato(insumos_usados, plato["mano_obra"])
        m = margen(plato["precio_venta"], costo)

        self.resultado_box.add_widget(MDLabel(
            text=f"+ Mano de obra: ${plato['mano_obra']:,.0f}",
            theme_text_color="Secondary", size_hint_y=None, height=dp(28),
        ))
        self.resultado_box.add_widget(MDLabel(
            text=f"Costo real total: ${costo:,.0f}",
            bold=True, size_hint_y=None, height=dp(32),
            theme_text_color="Custom", text_color=(1, 1, 1, 1),
        ))
        self.resultado_box.add_widget(MDLabel(
            text=f"Precio de venta: ${plato['precio_venta']:,.0f}   ·   Margen: {m:.1f}%",
            bold=True, size_hint_y=None, height=dp(32),
            theme_text_color="Custom", text_color=(0.2, 0.8, 0.4, 1) if m > 30 else
            ((0.95, 0.73, 0.13, 1) if m >= 10 else (0.9, 0.3, 0.3, 1)),
        ))