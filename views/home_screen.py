"""Inicio: saludo, aviso de unidades por confirmar, herramientas y resumen (prototipo del 2026-11-27)."""
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDIcon
from kivymd.uix.progressindicator import MDLinearProgressIndicator
from kivymd.uix.screen import MDScreen
from kivymd.uix.scrollview import MDScrollView

from models import confirmaciones, storage
from services import auth, escandallo
from views import estilo as e
from widgets.module_card import ModuleCard

MODULES = [
    ("Calcular costos", "Costo real y margen de cada plato", "calculator-variant-outline", "#0F766E", "#F0FDFA", "calcular_costos"),
    ("Menú", "Tus platos con foto, como una carta", "silverware-fork-knife", "#B45309", "#FFFBEB", "menu_visual"),
    ("Ingeniería de menú", "Rentabilidad de cada plato", "chart-bar", "#1D4ED8", "#EFF6FF", "ingenieria_de_menu"),
    ("Mis recetas", "Platos, insumos e ingredientes", "book-open-variant", "#C2410C", "#FFF7ED", "mis_recetas"),
    ("Plantillas", "Platos base para empezar rápido", "file-document-outline", "#6D28D9", "#F5F3FF", "mis_plantillas"),
    ("Acerca de", "La app y soporte", "information-outline", "#52525B", "#F4F4F5", "acerca_de"),
]


class HomeScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="inicio", md_bg_color=e.FONDO, **kwargs)
        scroll = MDScrollView(do_scroll_x=False)
        self.contenido = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(22), padding=(dp(36), dp(28)))
        scroll.add_widget(self.contenido)
        self.add_widget(scroll)

        cabecera = MDBoxLayout(adaptive_height=True, spacing=dp(12))
        textos = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(4))
        self.lbl_saludo = e.etiqueta("", "titulo", negrita=True)
        textos.add_widget(self.lbl_saludo)
        textos.add_widget(e.etiqueta("¿Qué quieres hacer hoy?", "cuerpo", e.TEXTO))
        cabecera.add_widget(textos)
        salir = e.boton("Cerrar sesión", self._cerrar_sesion, tipo="borde", alto=dp(36), ancho=dp(140))
        salir.pos_hint = {"center_y": 0.5}
        cabecera.add_widget(salir)
        self.contenido.add_widget(cabecera)

        self.slot_aviso = MDBoxLayout(orientation="vertical", adaptive_height=True)
        self.aviso = self._armar_aviso()
        self.contenido.add_widget(self.slot_aviso)

        self.contenido.add_widget(e.etiqueta("HERRAMIENTAS", "etiqueta", e.TEXTO_TENUE, negrita=True))
        self.grid = MDGridLayout(cols=3, spacing=dp(14), adaptive_height=True)
        self.tarjetas = []
        for titulo, texto, icono, color, fondo, pantalla in MODULES:
            card = ModuleCard(title=titulo, subtitle=texto, icon=icono, icon_color=get_color_from_hex(color),
                              tile_color=get_color_from_hex(fondo))
            card.bind(on_release=lambda _w, p=pantalla: setattr(self.manager, "current", p))
            card.bind(natural=self._igualar_filas)
            self.grid.add_widget(card)
            self.tarjetas.append(card)
        self.contenido.add_widget(self.grid)

        self.contenido.add_widget(e.etiqueta("RESUMEN", "etiqueta", e.TEXTO_TENUE, negrita=True))
        self.kpis = MDGridLayout(cols=3, spacing=dp(14), adaptive_height=True)
        self.kpi = [self._kpi() for _ in range(3)]
        self.contenido.add_widget(self.kpis)
        self.bind(width=self._acomodar)

    def _armar_aviso(self):
        aviso = MDCard(style="outlined", theme_bg_color="Custom", md_bg_color=e.BLANCO, theme_line_color="Custom",
                       line_color=e.BORDE, radius=[dp(12)], orientation="horizontal", padding=(dp(18), dp(16)),
                       spacing=dp(16), size_hint_y=None, height=dp(74), ripple_behavior=True)
        aviso.bind(on_release=lambda *_: setattr(self.manager, "current", "confirmar_unidades"))
        cuadro = MDBoxLayout(size_hint=(None, None), size=(dp(40), dp(40)), md_bg_color=e.AMBAR_FONDO, radius=[dp(10)],
                             pos_hint={"center_y": 0.5})
        cuadro.add_widget(MDIcon(icon="scale-balance", theme_text_color="Custom", text_color=e.AMBAR,
                                 pos_hint={"center_x": 0.5, "center_y": 0.5}))
        aviso.add_widget(cuadro)
        textos = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(7), pos_hint={"center_y": 0.5})
        fila = MDBoxLayout(adaptive_height=True, spacing=dp(4))
        self.fila_aviso = fila
        fila.add_widget(e.etiqueta("Confirma las unidades de tus insumos", "cuerpo", negrita=True))
        self.lbl_aviso = e.etiqueta("", "pequeno", e.TEXTO, halign="right")
        fila.add_widget(self.lbl_aviso)
        textos.add_widget(fila)
        self.barra_aviso = MDLinearProgressIndicator(size_hint_y=None, height=dp(6), value=0, indicator_color=e.ACENTO,
                                                     track_color=e.BORDE_SUAVE)
        textos.add_widget(self.barra_aviso)
        aviso.add_widget(textos)
        textos.bind(height=lambda _w, h: setattr(aviso, "height", max(dp(74), h + dp(32))))
        aviso.add_widget(MDIcon(icon="chevron-right", theme_text_color="Custom", text_color=e.GRIS, size_hint_x=None,
                                width=dp(22), pos_hint={"center_y": 0.5}))
        return aviso

    def _kpi(self):
        t = e.tarjeta(padding=(dp(18), dp(16)), spacing=dp(4))
        titulo = e.etiqueta("", "pequeno", e.TEXTO_TENUE)
        valor = e.etiqueta("", "titulo", negrita=True)
        detalle = e.etiqueta("", "pequeno", e.TEXTO, markup=True)
        for w in (titulo, valor, detalle):
            t.add_widget(w)
        self.kpis.add_widget(t)
        return titulo, valor, detalle

    def _acomodar(self, *args):
        ancho = self.width
        self.grid.cols = 3 if ancho >= dp(900) else 2 if ancho >= dp(560) else 1
        self.kpis.cols = 3 if ancho >= dp(900) else 1
        angosta = ancho < dp(600)
        self.fila_aviso.orientation = "vertical" if angosta else "horizontal"
        self.lbl_aviso.halign = "left" if angosta else "right"
        relleno = dp(36) if ancho >= dp(760) else dp(16)
        self.contenido.padding = (relleno, dp(28) if relleno > dp(20) else dp(20))
        self._igualar_filas()

    def _igualar_filas(self, *args):
        n = self.grid.cols
        for i in range(0, len(self.tarjetas), n):
            fila = self.tarjetas[i:i + n]
            alto = max(t.natural for t in fila)
            for t in fila:
                t.height = alto

    def on_pre_enter(self, *args):
        usuario = auth.usuario_actual
        self.lbl_saludo.text = f"Hola, {usuario}" if usuario else "Hola"
        insumos = storage.get_insumos()
        self._actualizar_aviso(insumos)
        self._actualizar_resumen(insumos)

    def _actualizar_aviso(self, insumos):
        self.slot_aviso.clear_widgets()
        try:
            listos = confirmaciones.resumen(insumos)[confirmaciones.CONFIRMADO]
        except confirmaciones.ErrorConfirmacion:
            return
        total = len(insumos)
        if total == 0 or listos == total:
            return
        self.lbl_aviso.text = f"{listos} de {total} listos · así podrás llevar inventario"
        self.barra_aviso.value = 100 * listos / total
        self.slot_aviso.add_widget(self.aviso)

    def _actualizar_resumen(self, insumos):
        resumen = escandallo.resumen_platos()
        (t1, v1, d1), (t2, v2, d2), (t3, v3, d3) = self.kpi
        t1.text, t2.text, t3.text = "Margen promedio del menú", "Plato más rentable", "Insumos registrados"
        if resumen:
            promedio = sum(r.margen for _, r in resumen) / len(resumen)
            v1.text, v1.text_color = e.porcentaje(promedio), e.TONO[e.tono_margen(promedio)][1]
            perdidas = sum(1 for _, r in resumen if r.margen < 0)
            d1.text = (f"{perdidas} de {len(resumen)} platos con pérdida." if perdidas else
                       f"{len(resumen)} platos en el menú.")
            plato, r = resumen[0]
            v2.text = e.capitalizar(plato["nombre"])
            d2.text = f"[color=#15803D][b]{e.porcentaje(r.margen)}[/b][/color] de margen · {e.pesos(r.utilidad)} por venta"
        else:
            v1.text, d1.text, v2.text, d2.text = "—", "Aún no hay platos.", "—", ""
        v3.text = str(len(insumos))
        try:
            sin = confirmaciones.resumen(insumos)[confirmaciones.PENDIENTE]
        except confirmaciones.ErrorConfirmacion:
            sin = 0
        d3.text = f"{sin} con la unidad sin confirmar" if sin else "Todas las unidades confirmadas"

    def _cerrar_sesion(self):
        auth.cerrar_sesion()
        self.manager.current = "login"
