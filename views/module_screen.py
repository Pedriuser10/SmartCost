"""Pantalla base para los módulos que aún no tienen funcionalidad propia."""
from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDButton , MDButtonText

class ModuleScreen(MDScreen):
    def __init__(self, title, description, **kwargs):
        super().__init__(md_bg_color=(0.95, 0.95, 0.95, 1), **kwargs)
        layout = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(18))

        back = MDButton(MDButtonText(text="‹  Volver al inicio", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48))
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "inicio"))
        layout.add_widget(back)

        layout.add_widget(
            MDLabel(text=title, font_style="Headline", role="medium", theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1), bold=True, size_hint_y=None, height=dp(52))
        )
        layout.add_widget(
            MDLabel(text=description, font_style="Title", role="medium", theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1))
        )

        self.content = MDLabel(
            text="Esta sección está lista para que agregues tus datos.",
            theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1)
        )
        layout.add_widget(self.content)
        self.add_widget(layout)