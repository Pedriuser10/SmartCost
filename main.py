from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager
from views.login_screen import LoginScreen
from views.home_screen import HomeScreen 
from views.module_screen import ModuleScreen
from views.cost_calculator_screen import CostCalculatorScreen
from views.recetas_screen import RecetasScreen
from views.ingenieria_menu_screen import IngenieriaMenuScreen
from views.menu_visual_screen import MenuVisualScreen
from views.plantillas_screen import PlantillasScreen
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.modalview import ModalView
from kivymd.uix.dialog import MDDialog
from kivymd.uix.filemanager import MDFileManager
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.screen import MDScreen
from kivymd.uix.label import MDLabel
from models import rutas

TECLA_ATRAS = 27  # botón Atrás de Android (Escape en el PC)
PANTALLAS_RAIZ = ("login", "inicio")  # desde aquí, Atrás deja que Android salga de la app


def cerrar_ventana_superior():
    """Cierra el diálogo, menú o selector de archivos abierto encima de la app. True si había uno."""
    for widget in Window.children:  # el primero es el que está más arriba
        # Mientras dura la animación de cierre siguen en la ventana: se saltan para que un
        # segundo Atrás rápido navegue en vez de "cerrar" otra vez lo que ya se está cerrando
        if getattr(widget, "_is_open", True) is False or getattr(widget, "_cerrando_por_atras", False):
            continue
        if isinstance(widget, (MDDialog, MDDropdownMenu)):
            widget._cerrando_por_atras = True
            widget.dismiss()
            return True
        if isinstance(widget, ModalView):
            selector = next((w for w in widget.walk(restrict=True) if isinstance(w, MDFileManager)), None)
            if selector is not None:
                selector.close()  # para subir de carpeta está la flecha de su propia barra
            else:
                widget.dismiss()
            return True
    return False


def pantalla_error_datos(mensaje):
    """Se muestra en lugar de la app si no se pudieron preparar los datos: así no se
    lee ni se escribe nada hasta resolverlo (no se crea una base de usuarios vacía)."""
    screen = MDScreen(md_bg_color=(0.97, 0.97, 0.99, 1))
    screen.add_widget(MDLabel(
        text=f"SmartCost no pudo abrir sus datos y se detuvo para no perder información.\n\n{mensaje}",
        halign="center", padding=(dp(24), dp(24)),
        theme_text_color="Custom", text_color=(0.8, 0.2, 0.2, 1),
    ))
    return screen


class SmartCostApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Teal"  # turquesa de la marca (views/marca.py)

        # Los datos (cuentas, recetas, fotos) viven en user_data_dir para sobrevivir a las actualizaciones
        try:
            rutas.configurar(self.user_data_dir)  # Kivy crea la carpeta si no existe
        except OSError as e:
            return pantalla_error_datos(f"No se pudo crear la carpeta de datos: {e}")
        if not rutas.migrar():
            return pantalla_error_datos(rutas.error)

        # El teclado del teléfono desplaza la pantalla para no tapar el campo que se está escribiendo
        Window.softinput_mode = "below_target"
        Window.bind(on_keyboard=self._tecla)

        sm = ScreenManager()
        pantallas = [LoginScreen, HomeScreen, CostCalculatorScreen, RecetasScreen, IngenieriaMenuScreen, MenuVisualScreen, PlantillasScreen]

   
        for pantalla in pantallas:
            sm.add_widget(pantalla())
            
       
        sm.add_widget(ModuleScreen(
            name="configuracion", 
            title="Configuración", 
            description="Ajusta parámetros, unidades y moneda"
        ))
        
        sm.add_widget(ModuleScreen(
            name="acerca_de", 
            title="Acerca de", 
            description="App para calcular costos reales y controlar la rentabilidad del menú en pequeños negocios gastronómicos. Python + Kivy/KivyMD + JSON."
        ))

        return sm

    def _tecla(self, window, tecla, *args):
        """Atrás cierra lo que esté abierto o vuelve al inicio, en vez de cerrar la app."""
        if tecla != TECLA_ATRAS or not isinstance(self.root, ScreenManager):
            return False
        if cerrar_ventana_superior():
            return True
        if self.root.current in PANTALLAS_RAIZ:
            return False  # Android sale de la app como siempre
        self.root.current = "inicio"
        return True

if __name__ == "__main__":
    SmartCostApp().run()