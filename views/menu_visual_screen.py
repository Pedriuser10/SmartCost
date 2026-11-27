"""Menú: los platos como una carta, con foto, precio y margen (prototipo aprobado el 2026-11-27)."""
from kivy.metrics import dp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.fitimage import FitImage
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDIcon
from kivymd.uix.screen import MDScreen
from kivymd.uix.scrollview import MDScrollView

from models import storage
from services import escandallo
from views import estilo as e


class DishCard(MDCard):
    def __init__(self, plato, resultado, al_ver, **kwargs):
        super().__init__(style="outlined", theme_bg_color="Custom", md_bg_color=e.BLANCO, theme_line_color="Custom",
                         line_color=e.BORDE, radius=[dp(12)], orientation="vertical", size_hint_y=None,
                         height=dp(300), ripple_behavior=True, **kwargs)
        self.bind(on_release=lambda *_: al_ver(plato))
        self.foto = MDBoxLayout(size_hint_y=None, height=dp(160), md_bg_color=e.BORDE_SUAVE, radius=[dp(12), dp(12), 0, 0])
        ruta = storage.ruta_imagen(plato.get("imagen"))
        if ruta:
            self.foto.add_widget(FitImage(source=ruta, radius=[dp(12), dp(12), 0, 0]))
        else:
            self.foto.add_widget(MDIcon(icon="silverware-fork-knife", halign="center", theme_font_size="Custom",
                                        font_size="48sp", theme_text_color="Custom", text_color=e.GRIS,
                                        pos_hint={"center_y": 0.5}))
        self.add_widget(self.foto)
        self.bind(width=self._proporcion)

        info = MDBoxLayout(orientation="vertical", adaptive_height=True, padding=(dp(16), dp(14), dp(16), dp(16)),
                           spacing=dp(8))
        cabeza = MDBoxLayout(adaptive_height=True, spacing=dp(10))
        cabeza.add_widget(e.etiqueta(e.capitalizar(plato["nombre"]), "subtitulo", negrita=True))
        pill = e.pildora(e.porcentaje(resultado.margen), e.tono_margen(resultado.margen))
        pill.pos_hint = {"top": 1}
        cabeza.add_widget(pill)
        info.add_widget(cabeza)
        info.add_widget(e.etiqueta(e.pesos(plato["precio_venta"]), "titulo", negrita=True))
        nota = "unidades por confirmar" if resultado.avisos else (
            "margen saludable" if resultado.margen >= 30 else "revisa el precio")
        info.add_widget(e.etiqueta(f"Costo real {e.pesos(resultado.costo)} · {nota}", "pequeno", e.TEXTO))
        info.add_widget(e.boton("Ver escandallo", lambda: al_ver(plato), tipo="borde", alto=dp(36)))
        self.add_widget(info)
        self.info = info
        info.bind(height=self._proporcion)

    def _proporcion(self, *args):
        self.foto.height = self.width * 9 / 16
        self.height = self.foto.height + self.info.height


class MenuVisualScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="menu_visual", md_bg_color=e.FONDO, **kwargs)
        scroll = MDScrollView(do_scroll_x=False)
        self.contenido = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(20), padding=(dp(36), dp(28)))
        scroll.add_widget(self.contenido)
        self.add_widget(scroll)

        cabecera = MDBoxLayout(adaptive_height=True)
        textos = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(4))
        textos.add_widget(e.etiqueta("Inicio / Menú", "pequeno", e.TEXTO_TENUE))
        textos.add_widget(e.etiqueta("Menú", "titulo", negrita=True))
        textos.add_widget(e.etiqueta("Tus platos como una carta. Toca uno para ver su escandallo.", "cuerpo", e.TEXTO))
        cabecera.add_widget(textos)
        self.lbl_total = e.etiqueta("", "cuerpo", e.TEXTO, halign="right", pos_hint={"center_y": 0.3})
        self.lbl_total.size_hint_x, self.lbl_total.width = None, dp(100)
        cabecera.add_widget(self.lbl_total)
        self.contenido.add_widget(cabecera)

        self.grid = MDGridLayout(cols=3, spacing=dp(18), adaptive_height=True)
        self.contenido.add_widget(self.grid)
        self.bind(width=self.ajustar_columnas)

    def ajustar_columnas(self, *args):
        ancho = self.width
        self.grid.cols = 3 if ancho > dp(1000) else 2 if ancho > dp(560) else 1
        relleno = dp(36) if ancho >= dp(760) else dp(16)
        self.contenido.padding = (relleno, dp(28) if relleno > dp(20) else dp(20))

    def on_pre_enter(self, *args):
        self.refrescar()

    def refrescar(self):
        self.grid.clear_widgets()
        resumen = {p["id"]: r for p, r in escandallo.resumen_platos()}
        platos = storage.get_platos()
        self.lbl_total.text = f"{len(platos)} {'plato' if len(platos) == 1 else 'platos'}"
        if not platos:
            self.grid.add_widget(e.etiqueta("Aún no tienes platos. Créalos desde Mis recetas.", "cuerpo", e.TEXTO))
            return
        for plato in platos:
            self.grid.add_widget(DishCard(plato, resumen[plato["id"]], self._ver_detalle))

    def _ver_detalle(self, plato):
        calculadora = self.manager.get_screen("calcular_costos")
        calculadora.seleccionar_plato_externo(plato)
        self.manager.current = "calcular_costos"
