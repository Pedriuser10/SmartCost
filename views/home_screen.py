from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.fitimage import FitImage

from widgets.module_card import ModuleCard


MODULES = [
    ("Calcular Costos", "Calcula el costo real de tus platos y recetas",
     "calculator", (0.2, 0.8, 0.4, 1), "calcular_costos"),
    ("Menú", "Tus platos con foto, estilo carta visual",
     "silverware-fork-knife", (0.95, 0.6, 0.1, 1), "menu_visual"),
    ("Ingeniería de Menú", "Analiza la rentabilidad y popularidad del menú",
     "chart-bar", (0.2, 0.6, 1, 1), "ingenieria_de_menu"),
    ("Mis Recetas", "Administra tus recetas e ingredientes",
     "book-open-variant", (1, 0.6, 0.2, 1), "mis_recetas"),
    ("Mis Plantillas", "Acelera tus cálculos con plantillas base",
     "file-document-outline", (0.6, 0.4, 0.9, 1), "mis_plantillas"),
    ("Configuración", "Ajusta parámetros, unidades y moneda",
     "cog-outline", (0.6, 0.6, 0.6, 1), "configuracion"),
    ("Acerca de", "Información de la app y soporte técnico",
     "information-outline", (0.9, 0.3, 0.3, 1), "acerca_de"),
]


class HomeScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="inicio", **kwargs)

        main_layout = MDFloatLayout()

        fondo = FitImage(
            source="data/images/Fondo_chef.png",
            size_hint=(1, 1)
        )
        main_layout.add_widget(fondo)

        overlay = MDBoxLayout(
            size_hint=(1, 1),
            md_bg_color=(0.15, 0.08, 0.05, 0.75)
        )
        main_layout.add_widget(overlay)

        content = MDBoxLayout(
            orientation="vertical",
            padding=[dp(32), dp(24)],
            spacing=dp(24),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            size_hint=(0.9, 0.9),
        )

        header_box = MDBoxLayout(orientation="vertical", size_hint_y=None, height=dp(70), spacing=dp(4))
        header_box.add_widget(
            MDLabel(
                text="Costos Gastronómicos",
                font_style="Headline", role="medium",
                bold=True,
                halign="center",
                theme_text_color="Custom",
                text_color=(1, 0.9, 0.8, 1),
            )
        )
        header_box.add_widget(
            MDLabel(
                text="Calcula, organiza y haz crecer tu negocio",
                font_style="Title", role="medium",
                halign="center",
                theme_text_color="Custom",
                text_color=(0.8, 0.8, 0.8, 1),
            )
        )
        content.add_widget(header_box)

        grid = MDGridLayout(cols=2, spacing=dp(16), size_hint_y=1)
        for title, subtitle, icon, color, screen_name in MODULES:
            card = ModuleCard(title=title, subtitle=subtitle, icon=icon, icon_color=color)
            card.bind(on_release=lambda _w, name=screen_name: setattr(self.manager, "current", name))
            grid.add_widget(card)

        content.add_widget(grid)
        main_layout.add_widget(content)
        self.add_widget(main_layout)