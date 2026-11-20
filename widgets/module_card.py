from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivymd.uix.card import MDCard
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.label import MDLabel

ALTO_MINIMO = dp(150)  # las tarjetas no se achican por debajo de esto aunque su texto sea corto


class ModuleCard(MDCard):
    def __init__(self, title="", subtitle="", icon="", icon_color=(0.9, 0.6, 0.2, 1), **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = dp(16)
        self.spacing = dp(8)
        self.radius = [dp(16)]
        self.ripple_behavior = True
        self.line_color = (0.4, 0.25, 0.15, 0.6)

        top_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        top_box.add_widget(
            MDIconButton(
                icon=icon,
                theme_icon_color="Custom",
                icon_color=icon_color,
                pos_hint={"center_y": 0.5},
            )
        )
        self.add_widget(top_box)

        titulo = MDLabel(
            text=title,
            font_style="Title", role="large",
            bold=True,
            theme_text_color="Custom",
            text_color=(0.1, 0.1, 0.1, 1),
            size_hint_y=None,
            height=dp(28),
        )
        # En un teléfono el título puede ocupar dos líneas: crece en vez de pisar el subtítulo
        titulo.bind(texture_size=lambda t, s: setattr(t, "height", max(dp(28), s[1])))
        self.add_widget(titulo)

        subtitulo = MDLabel(
            text=subtitle,
            font_style="Label", role="medium",
            theme_text_color="Custom",
            text_color=(0.1, 0.1, 0.1, 1),
            size_hint_y=None,
        )
        subtitulo.bind(texture_size=lambda t, s: setattr(t, "height", s[1]))
        self.add_widget(subtitulo)
        self.add_widget(Widget())  # absorbe el espacio sobrante: el contenido queda arriba

        # El alto lo fija la pantalla de inicio según el contenido (en el teléfono el texto
        # ocupa más líneas que en el PC), igualando las dos tarjetas de cada fila
        self.size_hint_y = None
        self.height = ALTO_MINIMO
