"""Ingeniería de menú: margen de cada plato con línea base en 0 % y sugerencias (prototipo del 2026-11-27)."""
from decimal import Decimal

from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.screen import MDScreen
from kivymd.uix.scrollview import MDScrollView

from services import escandallo
from views import estilo as e

ROJO_BARRA = e.get_color_from_hex("#FCA5A5")
COLUMNAS = [("PLATO", None, "left"), ("PRECIO DE VENTA", dp(130), "right"),
            ("COSTO REAL", dp(120), "right"), ("MARGEN", dp(110), "right"), ("SUGERENCIA", dp(330), "left")]


def sugerencia(resultado):
    m = resultado.margen
    if m >= 30:
        return "Margen saludable"
    if m >= 10:
        return "Margen ajustado: revisa el precio"
    if m >= 0:
        return "Margen bajo: sube el precio o baja costos"
    if resultado.avisos:
        return "Pérdida: confirma las unidades de sus insumos (hoy suma paquetes completos) o sube el precio"
    return "Pérdida: sube el precio o revisa el costo de los insumos"


class BarraMargen(Widget):
    """Barra horizontal desde la línea de 0 %: verde si es positiva, rojo suave si es negativa."""

    def __init__(self, margen, minimo, maximo, **kw):
        super().__init__(size_hint_y=None, height=dp(24), **kw)
        self.margen, self.minimo, self.maximo = float(margen), float(minimo), float(maximo)
        self.bind(pos=self._dibujar, size=self._dibujar)

    def _dibujar(self, *args):
        self.canvas.clear()
        rango = (self.maximo - self.minimo) or 1.0

        def x_de(v):
            v = max(self.minimo, min(self.maximo, v))
            return self.x + (v - self.minimo) / rango * self.width

        cero, fin = x_de(0), x_de(self.margen)
        with self.canvas:
            Color(*e.FONDO)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(4)])
            Color(*(e.VERDE if self.margen >= 0 else ROJO_BARRA))
            izq = min(cero, fin)
            RoundedRectangle(pos=(izq, self.y + dp(3)), size=(max(abs(fin - cero), dp(2)), self.height - dp(6)),
                             radius=[dp(3)])
            Color(*e.TEXTO_TENUE)
            Rectangle(pos=(cero, self.y - dp(4)), size=(dp(1), self.height + dp(8)))


class IngenieriaMenuScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="ingenieria_de_menu", md_bg_color=e.FONDO, **kwargs)
        self.recortada = False
        scroll = MDScrollView(do_scroll_x=False)
        self.contenido = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(20), padding=(dp(36), dp(28)))
        scroll.add_widget(self.contenido)
        self.add_widget(scroll)

        textos = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(4))
        textos.add_widget(e.etiqueta("Inicio / Ingeniería de menú", "pequeno", e.TEXTO_TENUE))
        textos.add_widget(e.etiqueta("Ingeniería de menú", "titulo", negrita=True))
        textos.add_widget(e.etiqueta("Rentabilidad de cada plato con la fórmula actual de costos.", "cuerpo", e.TEXTO))
        self.contenido.add_widget(textos)

        self.grafico = e.tarjeta(padding=(dp(20), dp(18)), spacing=dp(14))
        enc = MDBoxLayout(adaptive_height=True)
        enc.add_widget(e.etiqueta("Margen por plato", "subtitulo", negrita=True))
        self.seg_escala = e.Segmentado(None, [("prop", "Proporcional"), ("rec", "Recortada ±100 %")],
                                       self._escala, activo="prop")
        for b in self.seg_escala.botones.values():
            b.width = dp(140)
        enc.add_widget(self.seg_escala)
        self.grafico.add_widget(enc)
        self.barras = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(12))
        self.grafico.add_widget(self.barras)
        self.lbl_eje = e.etiqueta("", "pequeno", e.TEXTO_TENUE)
        self.grafico.add_widget(self.lbl_eje)
        self.contenido.add_widget(self.grafico)

        self.tabla = e.tarjeta(padding=0)
        self.contenido.add_widget(self.tabla)
        self.bind(width=self._acomodar)

    def _acomodar(self, *args):
        relleno = dp(36) if self.width >= dp(760) else dp(16)
        self.contenido.padding = (relleno, dp(28) if relleno > dp(20) else dp(20))
        compacta = self.width < dp(900)
        if compacta != getattr(self, "_compacta", None):
            self._compacta = compacta
            if self.manager is not None:
                self.refrescar()

    def on_pre_enter(self, *args):
        self.refrescar()

    def _escala(self, clave):
        self.recortada = clave == "rec"
        self.refrescar()

    def refrescar(self):
        resumen = escandallo.resumen_platos()
        self.barras.clear_widgets()
        self.tabla.clear_widgets()
        if not resumen:
            self.barras.add_widget(e.etiqueta("Aún no hay platos. Créalos en Mis recetas.", "cuerpo", e.TEXTO))
            self.lbl_eje.text = ""
            return
        margenes = [r.margen for _, r in resumen]
        minimo = Decimal(-100) if self.recortada else min(Decimal(0), *margenes)
        maximo = Decimal(100) if self.recortada else max(Decimal(0), *margenes)
        compacta = self.width < dp(900)
        for plato, r in resumen:
            fila = MDBoxLayout(size_hint_y=None, height=dp(24), spacing=dp(12))
            nombre = e.celda(e.capitalizar(plato["nombre"]), dp(120) if compacta else dp(180))
            valor = e.celda(e.porcentaje(r.margen), dp(84), "right", negrita=True, color=e.TONO[e.tono_margen(r.margen)][1])
            fila.add_widget(nombre)
            fila.add_widget(BarraMargen(r.margen, minimo, maximo))
            fila.add_widget(valor)
            self.barras.add_widget(fila)
        self.lbl_eje.text = (f"Escala de {e.porcentaje(minimo)} a {e.porcentaje(maximo)}; la línea marca el 0 %."
                             + (" Las barras que superan ±100 % llegan al borde." if self.recortada else ""))

        if not compacta:
            self.tabla.add_widget(e.encabezado_tabla(COLUMNAS))
        for plato, r in resumen:
            pill = e.pildora(e.porcentaje(r.margen), e.tono_margen(r.margen))
            if compacta:
                caja = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(4))
                caja.add_widget(e.celda(e.capitalizar(plato["nombre"]), negrita=True))
                caja.add_widget(e.celda(f"Venta {e.pesos(r.precio)} · costo {e.pesos(r.costo)}", estilo="pequeno",
                                        color=e.TEXTO))
                caja.add_widget(pill)
                caja.add_widget(e.celda(sugerencia(r), estilo="pequeno", color=e.TITULO))
                self.tabla.add_widget(e.fila_tabla([caja], relleno=dp(14)))
                continue
            margen = MDBoxLayout(size_hint_y=None, height=dp(26))
            margen.add_widget(Widget())
            margen.add_widget(pill)
            self.tabla.add_widget(e.fila_tabla([
                e.celda(e.capitalizar(plato["nombre"]), negrita=True),
                e.celda(e.pesos(r.precio), COLUMNAS[1][1], "right"),
                e.celda(e.pesos(r.costo), COLUMNAS[2][1], "right"),
                e.celda(margen, COLUMNAS[3][1]),
                e.celda(sugerencia(r), COLUMNAS[4][1], color=e.get_color_from_hex("#3F3F46")),
            ], alto_min=dp(52)))
