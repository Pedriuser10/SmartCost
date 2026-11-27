"""Calcular costos (escandallo), según el prototipo aprobado el 2026-11-27.

Todo lo que se edita aquí (porciones, cantidades, mano de obra, precio) es una simulación:
no modifica la receta guardada.
"""
from decimal import Decimal, InvalidOperation

from kivy.metrics import dp
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDIcon, MDLabel
from kivymd.uix.progressindicator import MDLinearProgressIndicator
from kivymd.uix.screen import MDScreen
from kivymd.uix.stacklayout import MDStackLayout
from kivymd.uix.scrollview import MDScrollView

from models import storage
from services import escandallo
from views import estilo as e

ANCHO_DOS_COLUMNAS = dp(980)
ANCHO_CABECERA_EN_FILA = dp(900)
ANCHO_TABLA_COMPLETA = dp(620)
COL_CANTIDAD, COL_PCT, COL_SUBTOTAL = dp(124), dp(150), dp(96)


def _numero(texto):
    try:
        v = Decimal((texto or "").replace(",", ".").strip())
    except InvalidOperation:
        return None
    return v if v.is_finite() and v >= 0 else None


def _texto_numero(v):
    t = f"{Decimal(str(v)).normalize():f}"
    return t.replace(".", ",")


class CampoNumero(MDCard):
    """Campo numérico compacto con borde, para tablas."""

    def __init__(self, valor, al_cambiar, ancho=dp(70), alto=dp(32), grande=False, **kw):
        super().__init__(style="outlined", theme_bg_color="Custom", md_bg_color=e.BLANCO,
                         theme_line_color="Custom", line_color=e.BORDE, radius=[dp(6)],
                         size_hint=(None, None), size=(ancho, alto), padding=(dp(6), 0), **kw)
        self.entrada = TextInput(text=valor, multiline=False, input_filter=lambda s, _u: s if s in "0123456789.," else "",
                                 halign="right", background_normal="", background_active="",
                                 background_color=(0, 0, 0, 0), foreground_color=e.TITULO, cursor_color=e.ACENTO,
                                 font_size="17sp" if grande else "13sp", padding=(0, (alto - dp(18 if grande else 15)) / 2, 0, 0),
                                 write_tab=False)
        self.entrada.bind(text=lambda _w, t: al_cambiar(t))
        self.add_widget(self.entrada)

    @property
    def text(self):
        return self.entrada.text

    @text.setter
    def text(self, valor):
        self.entrada.text = valor


class FilaIngrediente(MDBoxLayout):
    """En pantallas angostas (compacta) el nombre va arriba y los números en una segunda línea."""

    def __init__(self, fila, al_cambiar, compacta=False, **kw):
        super().__init__(orientation="vertical" if compacta else "horizontal", adaptive_height=True,
                         padding=(dp(14) if compacta else dp(18), dp(10)), spacing=dp(8), **kw)
        self.rel_id = fila.rel_id
        izquierda = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(2))
        izquierda.add_widget(e.etiqueta(e.capitalizar(fila.nombre), "cuerpo", negrita=True))
        detalle = f"{e.pesos(fila.precio)} por «{fila.unidad_original}»"
        if fila.merma:
            detalle += f" · merma {e.porcentaje(fila.merma * 100, 0)}"
        izquierda.add_widget(e.etiqueta(detalle, "pequeno", e.TEXTO_TENUE))
        self.slot_aviso = MDBoxLayout(orientation="vertical", adaptive_height=True, padding=(0, dp(4), 0, 0))
        izquierda.add_widget(self.slot_aviso)
        self.add_widget(izquierda)
        numeros = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8)) if compacta else self

        cantidad = MDBoxLayout(size_hint=(None, None), size=(COL_CANTIDAD, dp(32)), spacing=dp(4))
        if not compacta:
            cantidad.add_widget(Widget())
        self.campo = CampoNumero(_texto_numero(fila.cantidad), lambda t: al_cambiar(self.rel_id, t), ancho=dp(64))
        cantidad.add_widget(self.campo)
        cantidad.add_widget(MDLabel(text=fila.unidad or "", size_hint_x=None, width=dp(42), font_style="Body",
                                    role="small", theme_text_color="Custom", text_color=e.TEXTO_TENUE))
        numeros.add_widget(cantidad)

        pct = MDBoxLayout(size_hint=(None, None), size=(COL_PCT, dp(32)), spacing=dp(8))
        if compacta:
            pct.size_hint_x = 1
        self.barra = MDLinearProgressIndicator(size_hint_y=None, height=dp(6), value=0, indicator_color=e.ACENTO,
                                               track_color=e.BORDE_SUAVE, pos_hint={"center_y": 0.5})
        self.lbl_pct = MDLabel(text="", size_hint_x=None, width=dp(48), halign="right", font_style="Body",
                               role="small", theme_text_color="Custom", text_color=e.TEXTO, pos_hint={"center_y": 0.5})
        pct.add_widget(self.barra)
        pct.add_widget(self.lbl_pct)
        numeros.add_widget(pct)

        self.lbl_subtotal = MDLabel(text="", size_hint=(None, None), size=(COL_SUBTOTAL, dp(32)), halign="right",
                                    font_style="Body", role="medium", bold=True, theme_text_color="Custom",
                                    text_color=e.TITULO)
        numeros.add_widget(self.lbl_subtotal)
        if compacta:
            self.add_widget(numeros)

    def actualizar(self, fila, costo_total):
        parte = fila.subtotal / costo_total * 100 if costo_total > 0 else Decimal(0)
        self.barra.value = float(min(parte, 100))
        self.lbl_pct.text = e.porcentaje(parte)
        self.lbl_subtotal.text = e.pesos(fila.subtotal)
        self.slot_aviso.clear_widgets()
        if fila.aviso:
            texto = fila.aviso + (f". Si lo confirmas: {e.pesos(fila.si_confirma)}" if fila.si_confirma is not None else "")
            caja = MDBoxLayout(adaptive_height=True, spacing=dp(5), padding=(dp(7), dp(3)),
                               md_bg_color=e.AMBAR_FONDO, radius=[dp(6)])
            caja.add_widget(MDIcon(icon="alert-circle-outline", theme_text_color="Custom", text_color=e.AMBAR_TEXTO,
                                   size_hint_x=None, width=dp(16), theme_font_size="Custom", font_size="13sp",
                                   pos_hint={"center_y": 0.5}))
            caja.add_widget(e.etiqueta(texto, "pequeno", e.AMBAR_TEXTO))
            self.slot_aviso.add_widget(caja)


class CostCalculatorScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="calcular_costos", md_bg_color=e.FONDO, **kwargs)
        self._plato = None
        self._porciones = Decimal(1)
        self._formula = "actual"
        self._cantidades, self._mano, self._precio = {}, None, None
        self._filas = {}

        scroll = MDScrollView(do_scroll_x=False)
        self.contenido = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(18),
                                     padding=(dp(36), dp(28)))
        scroll.add_widget(self.contenido)
        self.add_widget(scroll)

        self.cabecera = MDBoxLayout(adaptive_height=True, spacing=dp(16))
        textos = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(4))
        textos.add_widget(e.etiqueta("Inicio / Calcular costos", "pequeno", e.TEXTO_TENUE))
        textos.add_widget(e.etiqueta("Calcular costos", "titulo", negrita=True))
        textos.add_widget(e.etiqueta("Elige un plato y revisa su costo real calculado a partir de la receta.",
                                     "cuerpo", e.TEXTO))
        self.cabecera.add_widget(textos)
        controles = MDBoxLayout(adaptive_size=True, spacing=dp(10), pos_hint={"center_y": 0.5})
        self.controles = controles
        self.seg_porciones = e.Segmentado("Porciones", [("1", "1x"), ("5", "5x"), ("10", "10x")],
                                          self._elegir_porciones, activo="1")
        self.campo_libre = CampoNumero("", self._porciones_libres, ancho=dp(52), alto=dp(30))
        self.campo_libre.pos_hint = {"center_y": 0.5}
        self.seg_porciones.add_widget(self.campo_libre)
        self.seg_formula = e.Segmentado("Merma", [("actual", "× (1 + m)"), ("propuesta", "÷ (1 − m)")],
                                        self._elegir_formula, activo="actual")
        controles.add_widget(self.seg_porciones)
        controles.add_widget(self.seg_formula)
        self.cabecera.add_widget(controles)
        self.contenido.add_widget(self.cabecera)

        chips_scroll = MDScrollView(do_scroll_y=False, size_hint_y=None, height=dp(40), bar_width=0)
        self.chips = MDBoxLayout(adaptive_width=True, size_hint_y=None, height=dp(36), spacing=dp(8))
        chips_scroll.add_widget(self.chips)
        self.contenido.add_widget(chips_scroll)

        self.vacio = e.etiqueta("Aún no tienes platos. Crea el primero en Mis recetas.", "cuerpo", e.TEXTO)

        self.cuerpo = MDBoxLayout(adaptive_height=True, spacing=dp(20))
        self.cuerpo.add_widget(self._armar_tabla())
        self.cuerpo.add_widget(self._armar_rentabilidad())
        self.slot_cuerpo = MDBoxLayout(orientation="vertical", adaptive_height=True)
        self.contenido.add_widget(self.slot_cuerpo)
        self.bind(width=self._acomodar)

    # ---------- armado ----------

    def _armar_tabla(self):
        t = e.tarjeta(padding=0)
        self.tabla = t
        enc = MDBoxLayout(adaptive_height=True, padding=(dp(18), dp(14)))
        self.lbl_titulo = e.etiqueta("", "subtitulo", negrita=True)
        enc.add_widget(self.lbl_titulo)
        enc.add_widget(e.etiqueta("Simulación: no cambia tu receta", "pequeno", e.TEXTO_TENUE, halign="right"))
        t.add_widget(enc)
        columnas = MDBoxLayout(size_hint_y=None, height=dp(34), padding=(dp(18), 0), spacing=dp(8),
                               md_bg_color=e.FONDO)
        for texto, ancho, alin in (("INGREDIENTE", None, "left"), ("CANTIDAD", COL_CANTIDAD, "right"),
                                   ("% DEL COSTO", COL_PCT, "left"), ("SUBTOTAL", COL_SUBTOTAL, "right")):
            lbl = MDLabel(text=texto, font_style="Label", role="medium", bold=True, halign=alin,
                          theme_text_color="Custom", text_color=e.TEXTO_TENUE)
            if ancho:
                lbl.size_hint_x, lbl.width = None, ancho
            columnas.add_widget(lbl)
        self.columnas = columnas
        t.add_widget(columnas)
        self.filas_box = MDBoxLayout(orientation="vertical", adaptive_height=True)
        t.add_widget(self.filas_box)
        pie = MDBoxLayout(orientation="vertical", adaptive_height=True, padding=(dp(18), dp(12)), spacing=dp(8),
                          md_bg_color=e.FONDO)
        self.lbl_subtotal = self._fila_total(pie, "Subtotal insumos")
        mano = MDBoxLayout(size_hint_y=None, height=dp(32))
        mano.add_widget(e.etiqueta("+ Mano de obra", "cuerpo", e.TEXTO, pos_hint={"center_y": 0.5}))
        mano.add_widget(MDLabel(text="$", size_hint_x=None, width=dp(14), halign="right", theme_text_color="Custom",
                                text_color=e.GRIS))
        self.campo_mano = CampoNumero("", self._cambiar_mano, ancho=dp(90))
        mano.add_widget(self.campo_mano)
        pie.add_widget(mano)
        self.lbl_costo = self._fila_total(pie, "Costo real total", negrita=True)
        t.add_widget(pie)
        return t

    def _fila_total(self, contenedor, texto, negrita=False):
        fila = MDBoxLayout(adaptive_height=True)
        fila.add_widget(e.etiqueta(texto, "subtitulo" if negrita else "cuerpo", e.TITULO if negrita else e.TEXTO,
                                   negrita=negrita))
        valor = e.etiqueta("", "subtitulo" if negrita else "cuerpo", e.TITULO if negrita else e.TEXTO,
                           negrita=negrita, halign="right")
        fila.add_widget(valor)
        contenedor.add_widget(fila)
        return valor

    def _armar_rentabilidad(self):
        r = e.tarjeta(padding=dp(18), spacing=dp(16))
        self.rentabilidad = r
        enc = MDBoxLayout(adaptive_height=True)
        enc.add_widget(e.etiqueta("Rentabilidad", "subtitulo", negrita=True))
        self.pildora_margen = e.pildora("", "verde")
        self.pildora_margen.pos_hint = {"center_y": 0.5}
        enc.add_widget(self.pildora_margen)
        r.add_widget(enc)

        precio = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(6))
        precio.add_widget(e.etiqueta("Precio de venta", "pequeno", e.TEXTO))
        fila = MDBoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        fila.add_widget(MDLabel(text="$", size_hint_x=None, width=dp(12), theme_text_color="Custom", text_color=e.GRIS))
        self.campo_precio = CampoNumero("", self._cambiar_precio, ancho=dp(200), alto=dp(42), grande=True)
        self.campo_precio.size_hint_x = 1
        fila.add_widget(self.campo_precio)
        precio.add_widget(fila)
        r.add_widget(precio)

        tiles = MDBoxLayout(adaptive_height=True, spacing=dp(10))
        self.lbl_costo_tile, self.lbl_utilidad = self._tile(tiles, "Costo real"), self._tile(tiles, "Utilidad neta")
        r.add_widget(tiles)

        dist = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(8))
        dist.add_widget(e.etiqueta("Distribución del precio", "pequeno", e.TEXTO))
        self.barra = MDBoxLayout(size_hint_y=None, height=dp(10), md_bg_color=e.BORDE_SUAVE, radius=[dp(5)])
        self.seg_ins = MDBoxLayout(md_bg_color=e.GRIS, size_hint_x=0)
        self.seg_mano = MDBoxLayout(md_bg_color=e.GRIS_CLARO, size_hint_x=0)
        self.seg_uti = MDBoxLayout(md_bg_color=e.VERDE, size_hint_x=0)
        self.seg_resto = Widget(size_hint_x=1)
        for w in (self.seg_ins, self.seg_mano, self.seg_uti, self.seg_resto):
            self.barra.add_widget(w)
        dist.add_widget(self.barra)
        leyenda = MDStackLayout(adaptive_height=True, spacing=(dp(12), dp(4)))
        self.ley = {}
        for clave, texto, color in (("ins", "Insumos", e.GRIS), ("mano", "Mano de obra", e.GRIS_CLARO),
                                    ("uti", "Utilidad", e.VERDE)):
            item = MDBoxLayout(adaptive_size=True, spacing=dp(5))
            item.add_widget(MDBoxLayout(size_hint=(None, None), size=(dp(8), dp(8)), md_bg_color=color,
                                        radius=[dp(2)], pos_hint={"center_y": 0.5}))
            lbl = MDLabel(text=texto, adaptive_size=True, font_style="Body", role="small", theme_text_color="Custom",
                          text_color=e.TEXTO)
            item.add_widget(lbl)
            self.ley[clave] = (lbl, texto)
            leyenda.add_widget(item)
        dist.add_widget(leyenda)
        r.add_widget(dist)

        self.slot_perdida = MDBoxLayout(orientation="vertical", adaptive_height=True)
        r.add_widget(self.slot_perdida)
        self.lbl_comparacion = e.etiqueta("", "pequeno", e.TEXTO)
        r.add_widget(self.lbl_comparacion)
        r.add_widget(e.boton("Restablecer valores de la receta", self._restablecer, tipo="borde"))
        return r

    def _tile(self, contenedor, titulo):
        caja = MDBoxLayout(orientation="vertical", adaptive_height=True, padding=(dp(12), dp(10)), spacing=dp(2),
                           md_bg_color=e.FONDO, radius=[dp(10)])
        caja.add_widget(e.etiqueta(titulo, "pequeno", e.TEXTO_TENUE))
        valor = e.etiqueta("", "grande", e.TITULO, negrita=True)
        caja.add_widget(valor)
        contenedor.add_widget(caja)
        return valor

    def _acomodar(self, *args):
        dos = self.width >= ANCHO_DOS_COLUMNAS
        self.cuerpo.orientation = "horizontal" if dos else "vertical"
        self.rentabilidad.size_hint_x = None if dos else 1
        self.rentabilidad.width = dp(330)
        self.rentabilidad.pos_hint = {"top": 1} if dos else {}
        self.cabecera.orientation = "horizontal" if self.width >= ANCHO_CABECERA_EN_FILA else "vertical"
        self.controles.orientation = "horizontal" if self.width >= dp(560) else "vertical"
        compacta = self.width < ANCHO_TABLA_COMPLETA
        self.columnas.opacity = 0 if compacta else 1
        self.columnas.height = 0 if compacta else dp(34)
        if compacta != getattr(self, "_compacta", None):
            self._compacta = compacta
            if self._plato is not None and self._filas:
                self._mostrar()
        relleno = dp(36) if self.width >= ANCHO_CABECERA_EN_FILA else dp(16)
        self.contenido.padding = (relleno, dp(28) if relleno > dp(20) else dp(20))

    # ---------- datos ----------

    def on_pre_enter(self, *args):
        platos = storage.get_platos()
        if self._plato is not None:
            self._plato = storage.get_plato(self._plato["id"])
        if self._plato is None and platos:
            self._plato = platos[0]
            self._reiniciar_simulacion()
        self._chips(platos)
        self._mostrar()

    def seleccionar_plato_externo(self, plato):
        """El Menú abre aquí el escandallo de un plato."""
        self._plato = plato
        self._reiniciar_simulacion()
        self._porciones = Decimal(1)
        self.campo_libre.text = ""
        self.seg_porciones.marcar("1")
        self._chips(storage.get_platos())
        self._mostrar()

    def _chips(self, platos):
        self.chips.clear_widgets()
        for p in platos:
            activo = self._plato is not None and p["id"] == self._plato["id"]
            nombre = e.capitalizar(p["nombre"])
            b = e.boton(nombre, lambda p=p: self._elegir_plato(p), tipo="primario" if activo else "borde",
                        alto=dp(36), ancho=dp(28) + dp(7.5) * len(nombre))
            self.chips.add_widget(b)

    def _elegir_plato(self, plato):
        self._plato = plato
        self._reiniciar_simulacion()
        self._chips(storage.get_platos())
        self._mostrar()

    def _reiniciar_simulacion(self):
        self._cantidades, self._mano, self._precio = {}, None, None

    def _mostrar(self):
        self.slot_cuerpo.clear_widgets()
        if self._plato is None:
            self.slot_cuerpo.add_widget(self.vacio)
            return
        self.slot_cuerpo.add_widget(self.cuerpo)
        self._acomodar()
        self.campo_mano.text = _texto_numero(self._mano if self._mano is not None else self._plato["mano_obra"])
        self.campo_precio.text = _texto_numero(self._precio if self._precio is not None else self._plato["precio_venta"])
        res = self._calcular()
        self.filas_box.clear_widgets()
        self._filas = {}
        for i, fila in enumerate(res.filas):
            w = FilaIngrediente(fila, self._cambiar_cantidad, compacta=self.width < ANCHO_TABLA_COMPLETA)
            if i:
                w.md_bg_color = e.BLANCO
            self._filas[fila.rel_id] = w
            self.filas_box.add_widget(w)
        self._pintar(res)

    def _calcular(self):
        return escandallo.calcular(self._plato, self._porciones, self._formula, self._cantidades,
                                   self._mano, self._precio)

    def _recalcular(self):
        if self._plato is not None:
            self._pintar(self._calcular())

    def _pintar(self, res):
        n = res.porciones
        self.lbl_titulo.text = f"{e.capitalizar(self._plato['nombre'])} · {_texto_numero(n)} " \
                               f"{'porción' if n == 1 else 'porciones'}"
        for fila in res.filas:
            if fila.rel_id in self._filas:
                self._filas[fila.rel_id].actualizar(fila, res.costo)
        self.lbl_subtotal.text = e.pesos(res.insumos)
        self.lbl_costo.text = e.pesos(res.costo)
        self.lbl_costo_tile.text = e.pesos(res.costo)
        self.lbl_utilidad.text = e.pesos(res.utilidad)
        self.lbl_utilidad.text_color = e.VERDE if res.utilidad >= 0 else e.ROJO
        e.cambiar_pildora(self.pildora_margen, f"Margen {e.porcentaje(res.margen)}", e.tono_margen(res.margen))

        total = max(res.precio, res.costo) or Decimal(1)
        utilidad = max(res.utilidad, Decimal(0))
        self.seg_ins.size_hint_x = float(res.insumos / total)
        self.seg_mano.size_hint_x = float(res.mano_obra / total)
        self.seg_uti.size_hint_x = float(utilidad / total)
        self.seg_resto.size_hint_x = max(0.0, 1 - float((res.insumos + res.mano_obra + utilidad) / total))
        for seg in (self.seg_ins, self.seg_mano, self.seg_uti):
            seg.opacity = 1 if seg.size_hint_x > 0 else 0
        precio = res.precio or Decimal(1)
        for clave, valor in (("ins", res.insumos / precio * 100), ("mano", res.mano_obra / precio * 100),
                             ("uti", max(res.margen, Decimal(0)))):
            lbl, texto = self.ley[clave]
            lbl.text = f"{texto} {e.porcentaje(valor)}"

        self.slot_perdida.clear_widgets()
        if res.utilidad < 0:
            caja = MDBoxLayout(adaptive_height=True, padding=(dp(11), dp(9)), md_bg_color=e.ROJO_FONDO, radius=[dp(8)])
            caja.add_widget(e.etiqueta(f"Pierdes {e.pesos(-res.utilidad / n)} por venta. Revisa las unidades sin "
                                       f"confirmar o el precio.", "pequeno", e.ROJO))
            self.slot_perdida.add_widget(caja)
        otra = "÷ (1 − merma)" if self._formula == "actual" else "× (1 + merma)"
        self.lbl_comparacion.text = (f"Con la fórmula {otra}: costo {e.pesos(res.costo_otra_formula)} · "
                                     f"margen {e.porcentaje(res.margen_otra_formula)}.")

    # ---------- interacción ----------

    def _elegir_porciones(self, clave):
        self.campo_libre.text = ""
        self._porciones = Decimal(clave)
        self._recalcular()

    def _porciones_libres(self, texto):
        v = _numero(texto)
        if v and v > 0:
            self._porciones = v
            self.seg_porciones.marcar(None)
        elif not texto:
            self._porciones = Decimal(self.seg_porciones.activo or 1)
            if self.seg_porciones.activo is None:
                self.seg_porciones.marcar("1")
                self._porciones = Decimal(1)
        self._recalcular()

    def _elegir_formula(self, formula):
        self._formula = formula
        self._recalcular()

    def _cambiar_cantidad(self, rel_id, texto):
        v = _numero(texto)
        if v is not None:
            self._cantidades[rel_id] = v
            self._recalcular()

    def _cambiar_mano(self, texto):
        v = _numero(texto)
        if v is not None and self._plato is not None:
            self._mano = v
            self._recalcular()

    def _cambiar_precio(self, texto):
        v = _numero(texto)
        if v is not None and self._plato is not None:
            self._precio = v
            self._recalcular()

    def _restablecer(self):
        self._reiniciar_simulacion()
        self._porciones = Decimal(1)
        self.campo_libre.text = ""
        self.seg_porciones.marcar("1")
        self._mostrar()
