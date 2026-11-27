"""Navegación principal: barra lateral fija en pantallas anchas y panel deslizable en el teléfono."""
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.modalview import ModalView
from kivy.uix.widget import Widget
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDIcon, MDLabel

from models import confirmaciones, storage
from views import estilo as e
from views import marca

ANCHO_BARRA = dp(240)
ANCHO_ESCRITORIO = dp(900)
SIN_NAVEGACION = ("login",)

PRINCIPAL = [
    ("inicio", "Inicio", "view-grid-outline"),
    ("calcular_costos", "Calcular costos", "calculator-variant-outline"),
    ("menu_visual", "Menú", "silverware-fork-knife"),
    ("ingenieria_de_menu", "Ingeniería de menú", "chart-bar"),
    ("mis_recetas", "Mis recetas", "book-open-variant"),
]
UTILIDADES = [
    ("mis_plantillas", "Plantillas", "file-document-outline"),
    ("acerca_de", "Acerca de", "information-outline"),
]
SECCION_DE = {"confirmar_unidades": "mis_recetas", "confirmar_insumo": "mis_recetas", "configuracion": "inicio"}


class ItemNavegacion(MDCard):
    def __init__(self, pantalla, texto, icono, al_tocar, **kw):
        super().__init__(style="filled", theme_bg_color="Custom", md_bg_color=e.BLANCO, radius=[dp(8)],
                         orientation="horizontal", size_hint_y=None, height=dp(40), padding=(dp(10), 0),
                         spacing=dp(10), **kw)
        self.pantalla = pantalla
        self.icono = MDIcon(icon=icono, theme_text_color="Custom", size_hint_x=None, width=dp(20),
                            pos_hint={"center_y": 0.5}, theme_font_size="Custom", font_size="18sp")
        self.texto = MDLabel(text=texto, font_style="Body", role="medium", theme_text_color="Custom",
                             pos_hint={"center_y": 0.5})
        self.insignia = e.pildora("", "ambar")
        self.insignia.pos_hint = {"center_y": 0.5}
        self.add_widget(self.icono)
        self.add_widget(self.texto)
        self.bind(on_release=lambda *_: al_tocar(pantalla))
        self.marcar(False)

    def marcar(self, activo):
        self.md_bg_color = e.ACENTO_FONDO if activo else e.BLANCO
        color = e.ACENTO if activo else e.get_color_from_hex("#3F3F46")
        self.icono.text_color = color
        self.texto.text_color = color
        self.texto.bold = activo

    def poner_insignia(self, n):
        if self.insignia.parent:
            self.remove_widget(self.insignia)
        if n:
            e.cambiar_pildora(self.insignia, str(n), "ambar")
            self.add_widget(self.insignia)


class BarraLateral(MDBoxLayout):
    def __init__(self, al_navegar, **kw):
        super().__init__(orientation="vertical", size_hint_x=None, width=ANCHO_BARRA,
                         padding=(dp(12), dp(18)), spacing=dp(4), md_bg_color=e.BLANCO, **kw)
        self._al_navegar = al_navegar
        with self.canvas.after:
            Color(*e.BORDE)
            self._borde = Rectangle()
        self.bind(pos=self._dibujar_borde, size=self._dibujar_borde)

        marca_fila = MDBoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10), padding=(dp(6), 0, 0, dp(14)))
        sello = MDBoxLayout(size_hint=(None, None), size=(dp(32), dp(32)), padding=dp(4),
                            md_bg_color=marca.AZUL_OSCURO, radius=[dp(9)], pos_hint={"center_y": 0.5})
        sello.add_widget(Image(source=marca.LOGO))
        marca_fila.add_widget(sello)
        textos = MDBoxLayout(orientation="vertical", pos_hint={"center_y": 0.5}, adaptive_height=True)
        textos.add_widget(e.etiqueta(marca.nombre_marca(), "subtitulo", negrita=True, markup=True))
        textos.add_widget(e.etiqueta("Gestión gastronómica", "pequeno", e.TEXTO_TENUE))
        marca_fila.add_widget(textos)
        self.add_widget(marca_fila)

        self.items = {}
        for titulo, grupo in (("PRINCIPAL", PRINCIPAL), ("UTILIDADES", UTILIDADES)):
            self.add_widget(MDLabel(text=titulo, font_style="Label", role="medium", bold=True,
                                    theme_text_color="Custom", text_color=e.GRIS, size_hint_y=None,
                                    height=dp(30), padding=(dp(10), 0)))
            for pantalla, texto, icono in grupo:
                item = ItemNavegacion(pantalla, texto, icono, self._al_navegar)
                self.items[pantalla] = item
                self.add_widget(item)
        self.add_widget(Widget())

        self.aviso = e.tarjeta(padding=dp(12), spacing=dp(6))
        self.aviso.md_bg_color = e.FONDO
        fila = MDBoxLayout(adaptive_height=True)
        fila.add_widget(e.etiqueta("Unidades", "pequeno", negrita=True))
        self.pildora_pendientes = e.pildora("", "ambar")
        fila.add_widget(self.pildora_pendientes)
        self.aviso.add_widget(fila)
        self.aviso.add_widget(e.etiqueta("Confírmalas para corregir los costos de los insumos comprados por paquete.",
                                         "pequeno", e.TEXTO))
        self.aviso.add_widget(e.boton("Confirmar unidades", lambda: self._al_navegar("confirmar_unidades"),
                                      tipo="borde", alto=dp(32)))
        self.add_widget(self.aviso)

    def _dibujar_borde(self, *args):
        self._borde.pos = (self.right - dp(1), self.y)
        self._borde.size = (dp(1), self.height)

    def actualizar(self, pantalla):
        seccion = SECCION_DE.get(pantalla, pantalla)
        for clave, item in self.items.items():
            item.marcar(clave == seccion)
        try:
            r = confirmaciones.resumen(storage.get_insumos())
            pendientes = r[confirmaciones.PENDIENTE] + r[confirmaciones.REVISAR]
        except Exception:
            pendientes = 0
        self.items["mis_recetas"].poner_insignia(pendientes)
        self.aviso.opacity = 1 if pendientes else 0
        self.aviso.disabled = not pendientes
        e.cambiar_pildora(self.pildora_pendientes, f"{pendientes} pendientes", "ambar")


class Contenedor(FloatLayout):
    """Raíz de la app: barra lateral + gestor de pantallas. Se comporta como el ScreenManager."""

    def __init__(self, sm, **kw):
        super().__init__(**kw)
        self.sm = sm
        self.fila = MDBoxLayout(md_bg_color=e.FONDO)
        self.fila.add_widget(sm)
        self.add_widget(self.fila)
        self.barra = BarraLateral(self.ir_a)
        self.panel = ModalView(size_hint=(None, 1), width=ANCHO_BARRA, pos_hint={"x": 0, "y": 0},
                               background_color=(0, 0, 0, 0), overlay_color=(0, 0, 0, 0.35))
        self.btn_menu = MDIconButton(icon="menu", style="filled", theme_bg_color="Custom", md_bg_color=e.TITULO,
                                     theme_icon_color="Custom", icon_color=e.BLANCO,
                                     pos_hint={"x": 0.03, "y": 0.02})
        self.btn_menu.bind(on_release=lambda *_: self.abrir_panel())
        sm.bind(current=self._actualizar)
        self.bind(width=self._actualizar)

    @property
    def current(self):
        return self.sm.current

    @current.setter
    def current(self, valor):
        self.sm.current = valor

    def get_screen(self, nombre):
        return self.sm.get_screen(nombre)

    def ir_a(self, pantalla):
        self.panel.dismiss()
        if self.sm.has_screen(pantalla):
            self.sm.current = pantalla

    def abrir_panel(self):
        if self.barra.parent:
            self.barra.parent.remove_widget(self.barra)
        self.panel.add_widget(self.barra)
        self.barra.actualizar(self.sm.current)
        self.panel.open()

    def _actualizar(self, *args):
        visible = self.sm.current not in SIN_NAVEGACION
        escritorio = self.width >= ANCHO_ESCRITORIO
        if visible and escritorio:
            if self.barra.parent is not self.fila:
                if self.barra.parent:
                    self.barra.parent.remove_widget(self.barra)
                self.fila.add_widget(self.barra, index=len(self.fila.children))
        elif self.barra.parent is self.fila:
            self.fila.remove_widget(self.barra)
        quiere_boton = visible and not escritorio
        if quiere_boton and self.btn_menu.parent is None:
            self.add_widget(self.btn_menu)
        elif not quiere_boton and self.btn_menu.parent is not None:
            self.remove_widget(self.btn_menu)
        if visible:
            self.barra.actualizar(self.sm.current)
