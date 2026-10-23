from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.fitimage import FitImage
from kivy.uix.widget import Widget
from kivymd.uix.button import MDButton , MDButtonText , MDButtonIcon
from widgets.module_card import ModuleCard
from kivymd.uix.card import MDCard

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
    ("Acerca de", "Información de la app y soporte técnico",
     "information-outline", (0.9, 0.3, 0.3, 1), "acerca_de"),
]


from kivymd.uix.button import MDButton, MDButtonText, MDButtonIcon
from kivy.uix.widget import Widget

class HomeScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="inicio", md_bg_color=(0.97, 0.97, 0.99, 1), **kwargs)

        # Contenedor principal vertical
        main_layout = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(16))

        # Barra superior con el botón de Configuración a la derecha
        top_bar = MDBoxLayout(size_hint_y=None, height=dp(48))
        top_bar.add_widget(Widget())  # Espaciador invisible para empujar el botón a la derecha
        
        btn_config = MDButton(
            MDButtonIcon(icon="cog-outline"),
            MDButtonText(text="Configuración"),
            style="text",
            on_release=lambda x: setattr(self.manager, "current", "configuracion")
        )
        top_bar.add_widget(btn_config)
        main_layout.add_widget(top_bar)

        # Títulos de la app
        header = MDBoxLayout(orientation="vertical", size_hint_y=None, height=dp(80), spacing=dp(4))
        header.add_widget(MDLabel(text="Costos Gastronómicos", font_style="Headline", role="medium", bold=True, halign="center"))
        header.add_widget(MDLabel(text="Calcula, organiza y haz crecer tu negocio", font_style="Title", role="medium", halign="center", theme_text_color="Secondary"))
        main_layout.add_widget(header)

        
        container = MDCard(
            style="outlined",
            line_color=(0.8, 0.85, 0.9, 1), 
            padding=dp(16),
            radius=[dp(16)],
            md_bg_color=(0.95, 0.96, 0.99, 1) 
        )
        
        # Cuadrícula de 6 módulos
        grid = MDGridLayout(cols=2, spacing=dp(16))
        for title, subtitle, icon, color, screen_name in MODULES:
            card = ModuleCard(title=title, subtitle=subtitle, icon=icon, icon_color=color, md_bg_color=color) # Ajusta los colores pastel en la lista MODULES
            card.bind(on_release=lambda _w, name=screen_name: setattr(self.manager, "current", name))
            grid.add_widget(card)
            
        container.add_widget(grid)
        main_layout.add_widget(container)
        self.add_widget(main_layout)