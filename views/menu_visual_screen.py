from kivy.metrics import dp
from kivymd.uix.fitimage import FitImage
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDButton, MDButtonText
from models import storage


class DishCard(MDCard):
    def __init__(self, plato, on_release=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.radius = [dp(14)]
        self.theme_bg_color = "Custom"
        self.md_bg_color = (1, 1, 1, 1)
        self.size_hint_y = None
        self.height = dp(220)
        self.ripple_behavior = True
        if on_release:
            self.bind(on_release=lambda *_: on_release(plato))

        # La foto se resuelve desde models.storage, no desde la carpeta actual
        imagen_path = storage.ruta_imagen(plato.get("imagen"))
        if imagen_path:
            foto = FitImage(source=imagen_path, size_hint_y=None, height=dp(140), radius=[dp(14), dp(14), 0, 0])
        else:
            foto = MDLabel(text="🍽", halign="center", font_style="Display", role="large", size_hint_y=None, height=dp(140), theme_text_color="Custom", text_color=(0.4, 0.4, 0.45, 1))
        self.add_widget(foto)
        info = MDBoxLayout(orientation="vertical", padding=dp(10), spacing=dp(2))
        info.add_widget(MDLabel(text=plato["nombre"], bold=True, font_style="Title", role="medium", theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1)))
        info.add_widget(MDLabel(text=f"${plato['precio_venta']:,.0f}", theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1)))
        self.add_widget(info)


class MenuVisualScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="menu_visual", md_bg_color=(0.95, 0.95, 0.95, 1), **kwargs)
        root = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(16))
        back = MDButton(MDButtonText(text="‹  Volver al inicio"), style="text", size_hint_y=None, height=dp(48))
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "inicio"))
        root.add_widget(back)
        root.add_widget(MDLabel(text="Menú", font_style="Headline", role="medium", bold=True, size_hint_y=None, height=dp(52), theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1)))
        scroll = MDScrollView()
        self.grid = MDGridLayout(spacing=dp(14), padding=(0, dp(8)), size_hint_y=None, cols=1)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll.add_widget(self.grid)
        root.add_widget(scroll)
        self.mensaje_vacio = MDLabel(text="Aún no tienes platos con foto. Agrégalos desde 'Mis Recetas'.", theme_text_color="Secondary")
        self.add_widget(root)
        self.bind(width=self.ajustar_columnas)

    def ajustar_columnas(self, *args):
        if self.width > 1200:
            self.grid.cols = 4
        elif self.width > 800:
            self.grid.cols = 3
        elif self.width > 500:
            self.grid.cols = 2
        else:
            self.grid.cols = 1

    def on_pre_enter(self, *args):
        self.refrescar()

    def refrescar(self):
        self.grid.clear_widgets()
        platos = storage.get_platos()
        if not platos:
            self.grid.add_widget(self.mensaje_vacio)
            return
        for plato in platos:
            self.grid.add_widget(DishCard(plato, on_release=self._ver_detalle))

    def _ver_detalle(self, plato):
        calculadora = self.manager.get_screen("calcular_costos")
        calculadora.seleccionar_plato_externo(plato)
        self.manager.current = "calcular_costos"