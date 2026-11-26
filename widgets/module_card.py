"""Tarjeta de una herramienta en la pantalla de inicio (diseño aprobado el 2026-11-26).

Blanca, con borde fino, el ícono en un cuadro de color, el título y una línea de texto.
"""
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDIcon, MDLabel

from views import marca

ALTO_MINIMO = dp(128)  # las tarjetas no se achican por debajo de esto aunque su texto sea corto
BORDE = get_color_from_hex("#E1E7EE")


class ModuleCard(MDCard):
    def __init__(self, title="", subtitle="", icon="", icon_color=(0.1, 0.5, 0.3, 1),
                 tile_color=(0.9, 0.95, 0.92, 1), **kwargs):
        super().__init__(style="outlined", theme_bg_color="Custom", md_bg_color=(1, 1, 1, 1),
                         theme_line_color="Custom", line_color=BORDE, **kwargs)
        self.orientation = "vertical"
        self.padding = dp(14)
        self.spacing = dp(10)
        self.radius = [dp(16)]
        self.ripple_behavior = True

        cuadro = MDBoxLayout(size_hint=(None, None), size=(dp(40), dp(40)), md_bg_color=tile_color,
                             radius=[dp(12)])
        cuadro.add_widget(MDIcon(icon=icon, theme_text_color="Custom", text_color=icon_color,
                                 pos_hint={"center_x": 0.5, "center_y": 0.5}))
        self.add_widget(cuadro)

        titulo = MDLabel(text=title, font_style="Title", role="medium", bold=True,
                         theme_text_color="Custom", text_color=marca.TEXTO, size_hint_y=None)
        # En un teléfono el título puede ocupar dos líneas: crece en vez de pisar el texto
        titulo.bind(texture_size=lambda t, s: setattr(t, "height", s[1]))
        self.add_widget(titulo)

        texto = MDLabel(text=subtitle, font_style="Body", role="small", theme_text_color="Custom",
                        text_color=marca.TEXTO_SUAVE, size_hint_y=None)
        texto.bind(texture_size=lambda t, s: setattr(t, "height", s[1]))
        self.add_widget(texto)
        self.add_widget(Widget())  # absorbe el espacio sobrante: el contenido queda arriba

        # El alto lo fija la pantalla de inicio según el contenido, igualando las tarjetas de cada fila
        self.size_hint_y = None
        self.height = ALTO_MINIMO
