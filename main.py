from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager
from models.storage import init_db
from views.home_screen import HomeScreen 
from views.module_screen import ModuleScreen
from views.cost_calculator_screen import CostCalculatorScreen
from views.recetas_screen import RecetasScreen
from views.ingenieria_menu_screen import IngenieriaMenuScreen
from views.menu_visual_screen import MenuVisualScreen
from views.plantillas_screen import PlantillasScreen
from views.module_screen import ModuleScreen

class SmartCostApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Orange"
        init_db()
        sm = ScreenManager()
        pantallas = [HomeScreen , CostCalculatorScreen , RecetasScreen , IngenieriaMenuScreen , MenuVisualScreen , PlantillasScreen]

        for pantalla in pantallas:
            sm.add_widget(pantalla())
            sm.add_widget(ModuleScreen(name="configuracion", title="Configuración", description="Ajusta parámetros, unidades y moneda"))
            sm.add_widget(ModuleScreen(name="acerca_de", title="Acerca de", description="App para calcular costos reales y controlar la rentabilidad del menú en " \
            "pequeños negocios gastronómicos. Python + Kivy/KivyMD + SQLite."))

        return sm
if __name__ == "__main__":
    SmartCostApp().run()