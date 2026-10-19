from kivy.metrics import dp
from kivymd.uix.card import MDCard
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.label import MDLabel


class ModuleCard(MDCard):
    def __init__(self, title="", subtitle="", icon="", icon_color=(0.9, 0.6, 0.2, 1), **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = dp(16)
        self.spacing = dp(8)
        self.radius = [dp(16)]
        self.ripple_behavior = True
        self.md_bg_color = (0.22, 0.15, 0.12, 0.85)
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

        self.add_widget(
            MDLabel(
                text=title,
                font_style="Title", role="large",
                bold=True,
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                size_hint_y=None,
                height=dp(28),
            )
        )

        self.add_widget(
            MDLabel(
                text=subtitle,
                font_style="Label", role="medium",
                theme_text_color="Custom",
                text_color=(0.6, 0.6, 0.6, 1),
            )
        )