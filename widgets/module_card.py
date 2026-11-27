"""Tarjeta de una herramienta en el inicio: ícono en un cuadro pastel, título y una línea de texto."""
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDIcon

from views import estilo as e

ALTO_MINIMO = dp(88)


class ModuleCard(MDCard):
    natural = NumericProperty(ALTO_MINIMO)

    def __init__(self, title="", subtitle="", icon="", icon_color=(0.06, 0.46, 0.43, 1),
                 tile_color=(0.94, 0.99, 0.98, 1), **kwargs):
        super().__init__(style="outlined", theme_bg_color="Custom", md_bg_color=e.BLANCO, theme_line_color="Custom",
                         line_color=e.BORDE, radius=[dp(12)], orientation="horizontal", padding=dp(16),
                         spacing=dp(14), ripple_behavior=True, size_hint_y=None, height=ALTO_MINIMO, **kwargs)
        cuadro = MDBoxLayout(size_hint=(None, None), size=(dp(40), dp(40)), md_bg_color=tile_color, radius=[dp(10)],
                             pos_hint={"top": 1})
        cuadro.add_widget(MDIcon(icon=icon, theme_text_color="Custom", text_color=icon_color,
                                 pos_hint={"center_x": 0.5, "center_y": 0.5}))
        self.add_widget(cuadro)
        textos = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(3), pos_hint={"top": 1})
        textos.add_widget(e.etiqueta(title, "subtitulo", negrita=True))
        textos.add_widget(e.etiqueta(subtitle, "pequeno", e.TEXTO))
        self.add_widget(textos)
        textos.bind(height=lambda _w, h: setattr(self, "natural", max(ALTO_MINIMO, h + dp(32))))
