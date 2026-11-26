"""Pantalla de inicio (diseño aprobado en el prototipo del 2026-11-26).

Marca arriba con Configuración y Cerrar sesión, saludo, un aviso con las unidades que
faltan por confirmar (solo mientras falten) y las herramientas en tarjetas.
"""
from kivy.metrics import dp
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.label import MDIcon, MDLabel
from kivymd.uix.progressindicator import MDLinearProgressIndicator
from kivymd.uix.screen import MDScreen
from kivymd.uix.scrollview import MDScrollView

from models import confirmaciones, storage
from services import auth
from views import marca
from views.fondo import FONDO, FondoPuntos
from views.utils import alto_segun_texto
from widgets.module_card import ALTO_MINIMO, ModuleCard

BORDE = get_color_from_hex("#E1E7EE")
BORDE_AVISO = get_color_from_hex("#B9DEDD")
ACENTO = marca.TURQUESA_OSCURO
ACENTO_SUAVE = get_color_from_hex("#E3F1F1")
ICONO_GRIS = get_color_from_hex("#4A5868")

# (título, texto, ícono, color del ícono, fondo del cuadro, pantalla)
MODULES = [
    ("Calcular costos", "Costo real y margen de tus platos", "calculator-variant-outline",
     "#1B7A43", "#E3F3EA", "calcular_costos"),
    ("Menú", "Tus platos con foto, como una carta", "silverware-fork-knife",
     "#A14700", "#FFF1DB", "menu_visual"),
    ("Ingeniería de menú", "Rentabilidad y popularidad", "chart-bar",
     "#1D5FBF", "#E3EEFC", "ingenieria_de_menu"),
    ("Mis recetas", "Platos, insumos e ingredientes", "book-open-variant",
     "#B3410E", "#FDE9DC", "mis_recetas"),
    ("Plantillas", "Platos base para empezar rápido", "file-document-outline",
     "#6D3FC0", "#EFE7FB", "mis_plantillas"),
    ("Acerca de", "La app y soporte", "information-outline",
     "#4A5868", "#EEF2F5", "acerca_de"),
]


def _etiqueta(texto, estilo=("Body", "medium"), color=marca.TEXTO, negrita=False, **kw):
    return alto_segun_texto(MDLabel(text=texto, font_style=estilo[0], role=estilo[1], bold=negrita,
                                    theme_text_color="Custom", text_color=color, **kw))


def _boton_icono(icono, al_tocar):
    b = MDIconButton(icon=icono, style="outlined", theme_icon_color="Custom", icon_color=ICONO_GRIS,
                     theme_line_color="Custom", line_color=BORDE, theme_bg_color="Custom",
                     md_bg_color=(1, 1, 1, 1), pos_hint={"center_y": 0.5})
    b.bind(on_release=lambda *_: al_tocar())
    return b


class HomeScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="inicio", md_bg_color=FONDO, **kwargs)
        self.add_widget(FondoPuntos())

        scroll = MDScrollView(do_scroll_x=False)
        raiz = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(20),
                           padding=(dp(20), dp(20), dp(20), dp(24)))

        # Barra superior: marca a la izquierda, Configuración y Cerrar sesión a la derecha
        barra = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        sello = MDBoxLayout(size_hint=(None, None), size=(dp(40), dp(40)), padding=dp(5),
                            md_bg_color=marca.AZUL_OSCURO, radius=[dp(11)], pos_hint={"center_y": 0.5})
        sello.add_widget(Image(source=marca.LOGO))
        barra.add_widget(sello)
        barra.add_widget(MDLabel(text=marca.nombre_marca(), markup=True, font_style="Title", role="large",
                                 bold=True, pos_hint={"center_y": 0.5}))
        barra.add_widget(_boton_icono("cog-outline", lambda: setattr(self.manager, "current", "configuracion")))
        barra.add_widget(_boton_icono("logout", self._cerrar_sesion))
        raiz.add_widget(barra)

        saludo = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(4),
                             padding=(0, dp(6), 0, 0))
        self.lbl_saludo = _etiqueta("", ("Headline", "small"), negrita=True)
        saludo.add_widget(self.lbl_saludo)
        saludo.add_widget(_etiqueta("¿Qué quieres hacer hoy?", ("Body", "large"), marca.TEXTO_SUAVE))
        raiz.add_widget(saludo)

        # Aviso de unidades por confirmar: se muestra solo mientras falten
        self.slot_aviso = MDBoxLayout(orientation="vertical", adaptive_height=True)
        self.aviso = self._armar_aviso()
        raiz.add_widget(self.slot_aviso)

        raiz.add_widget(_etiqueta("HERRAMIENTAS", ("Label", "large"), marca.TEXTO_SUAVE, negrita=True))
        grid = MDGridLayout(cols=2, spacing=dp(12), adaptive_height=True)
        self.grid = grid
        # 2 columnas en el teléfono, 3 cuando la ventana es ancha (PC o tablet)
        grid.bind(width=self._ajustar_columnas)
        self.tarjetas = []
        for titulo, texto, icono, color, fondo, pantalla in MODULES:
            card = ModuleCard(title=titulo, subtitle=texto, icon=icono, icon_color=get_color_from_hex(color),
                              tile_color=get_color_from_hex(fondo))
            card.bind(on_release=lambda _w, p=pantalla: setattr(self.manager, "current", p))
            card.bind(minimum_height=self._igualar_filas)
            grid.add_widget(card)
            self.tarjetas.append(card)
        raiz.add_widget(grid)

        scroll.add_widget(raiz)
        self.add_widget(scroll)

    def _armar_aviso(self):
        aviso = MDCard(style="outlined", theme_bg_color="Custom", md_bg_color=(1, 1, 1, 1),
                       theme_line_color="Custom", line_color=BORDE_AVISO, radius=[dp(16)],
                       orientation="horizontal", padding=(dp(16), dp(14), dp(12), dp(14)), spacing=dp(14),
                       size_hint_y=None, height=dp(80))
        aviso.bind(minimum_height=aviso.setter("height"))  # alto inicial ≠ 0 (ver views.utils)
        aviso.bind(on_release=lambda *_: setattr(self.manager, "current", "confirmar_unidades"))
        cuadro = MDBoxLayout(size_hint=(None, None), size=(dp(42), dp(42)), md_bg_color=ACENTO_SUAVE,
                             radius=[dp(12)], pos_hint={"center_y": 0.5})
        cuadro.add_widget(MDIcon(icon="scale-balance", theme_text_color="Custom", text_color=ACENTO,
                                 pos_hint={"center_x": 0.5, "center_y": 0.5}))
        aviso.add_widget(cuadro)
        textos = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(6),
                             pos_hint={"center_y": 0.5})
        textos.add_widget(_etiqueta("Confirma las unidades de tus insumos", ("Body", "large"), negrita=True))
        self.lbl_aviso = _etiqueta("", ("Body", "medium"), marca.TEXTO_SUAVE)
        textos.add_widget(self.lbl_aviso)
        self.barra_aviso = MDLinearProgressIndicator(size_hint_y=None, height=dp(6), value=0,
                                                     indicator_color=ACENTO, track_color=BORDE)
        textos.add_widget(self.barra_aviso)
        aviso.add_widget(textos)
        aviso.add_widget(MDIcon(icon="chevron-right", theme_text_color="Custom", text_color=marca.TEXTO_SUAVE,
                                size_hint_x=None, width=dp(24), pos_hint={"center_y": 0.5}))
        return aviso

    def on_pre_enter(self, *args):
        usuario = auth.usuario_actual
        self.lbl_saludo.text = f"Hola, {usuario}" if usuario else "Hola"
        self._actualizar_aviso()

    def _actualizar_aviso(self):
        self.slot_aviso.clear_widgets()
        try:
            insumos = storage.get_insumos()
            resumen = confirmaciones.resumen(insumos)
        except Exception:
            return  # si no se pueden leer los datos, simplemente no se muestra el aviso
        total = len(insumos)
        listos = resumen[confirmaciones.CONFIRMADO]
        if total == 0 or listos == total:
            return
        self.lbl_aviso.text = f"{listos} de {total} listos · así podrás llevar inventario"
        self.barra_aviso.value = 100 * listos / total
        self.slot_aviso.add_widget(self.aviso)

    def _ajustar_columnas(self, grid, ancho):
        columnas = 3 if ancho > dp(720) else 2
        if grid.cols != columnas:
            grid.cols = columnas
            self._igualar_filas()

    def _igualar_filas(self, *args):
        """Cada tarjeta mide lo que necesita su texto, y las de una misma fila quedan iguales."""
        n = self.grid.cols
        for i in range(0, len(self.tarjetas), n):
            fila = self.tarjetas[i:i + n]
            alto = max([ALTO_MINIMO] + [t.minimum_height for t in fila])
            for t in fila:
                t.height = alto

    def _cerrar_sesion(self):
        auth.cerrar_sesion()
        self.manager.current = "login"
