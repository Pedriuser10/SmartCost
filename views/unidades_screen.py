"""Pantalla para confirmar, insumo por insumo, su unidad base (D4/D6).

No modifica los insumos ni app.json: las decisiones se guardan aparte con
models/confirmaciones.py y se usarán al migrar a la base nueva.
"""
from decimal import Decimal

from kivy.metrics import dp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.dialog import MDDialog, MDDialogButtonContainer, MDDialogContentContainer, MDDialogHeadlineText
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.screen import MDScreen
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText

from models import confirmaciones as conf, storage
from services.calculo_costos import UNIDADES
from views.utils import alto_segun_texto, set_texto_boton

NOMBRE = "confirmar_unidades"
COLOR_ESTADO = {
    conf.PENDIENTE: (0.85, 0.55, 0.1, 1),
    conf.CONFIRMADO: (0.2, 0.6, 0.3, 1),
    conf.REVISAR: (0.85, 0.25, 0.25, 1),
}
TEXTO_ESTADO = {conf.PENDIENTE: "Pendiente", conf.CONFIRMADO: "Confirmado", conf.REVISAR: "Por revisar"}
COLOR_PRIMARIO = (0.1, 0.42, 0.42, 1)   # turquesa de la marca


def _pesos(valor, decimales=2):
    """$1.234,56 (formato chileno). Sin decimales si son cero."""
    texto = f"{Decimal(str(valor)):,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if "," in texto:
        texto = texto.rstrip("0").rstrip(",")
    return "$" + texto


def _numero(valor):
    texto = f"{Decimal(str(valor)).normalize():f}"
    return texto.replace(".", ",")


def unidades_de(base):
    return [codigo for codigo, (_d, b, _f) in UNIDADES.items() if b == base]


class UnidadesScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name=NOMBRE, md_bg_color=(0.95, 0.95, 0.95, 1), **kwargs)
        self.dialog = None
        self.menu = None

        root = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(12))
        back = MDButton(MDButtonText(text="‹  Volver a Mis Recetas"), style="text", size_hint_y=None, height=dp(48))
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "mis_recetas"))
        root.add_widget(back)
        root.add_widget(MDLabel(text="Confirmar unidades", font_style="Headline", role="medium", bold=True,
                                size_hint_y=None, height=dp(52), theme_text_color="Custom",
                                text_color=(0.1, 0.1, 0.1, 1)))
        root.add_widget(alto_segun_texto(MDLabel(
            text="Para llevar inventario y cotizar con el último precio, cada insumo necesita una unidad "
                 "base y saber a cuánto corresponde su precio. Revisa cada uno: nada se cambia solo, y tus "
                 "insumos y recetas siguen igual.",
            theme_text_color="Secondary")))
        self.resumen_lbl = MDLabel(text="", size_hint_y=None, height=dp(28), bold=True)
        root.add_widget(self.resumen_lbl)

        scroll = MDScrollView()
        self.container = MDBoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
        self.container.bind(minimum_height=self.container.setter("height"))
        scroll.add_widget(self.container)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_pre_enter(self, *args):
        self.refrescar()

    # ---------- lista ----------

    def refrescar(self):
        self.container.clear_widgets()
        try:
            datos = conf.cargar()
        except conf.ErrorConfirmacion as e:
            self.resumen_lbl.text = str(e)
            return
        insumos = storage.get_insumos()
        conteo = {conf.PENDIENTE: 0, conf.CONFIRMADO: 0, conf.REVISAR: 0}
        # Primero lo que falta revisar
        orden = {conf.REVISAR: 0, conf.PENDIENTE: 1, conf.CONFIRMADO: 2}
        filas = sorted(((conf.estado(i, datos), i) for i in insumos), key=lambda t: (orden[t[0]], t[1]["nombre"].lower()))
        for est, insumo in filas:
            conteo[est] += 1
            self.container.add_widget(self._fila(insumo, est, datos))
        self.resumen_lbl.text = (f"{conteo[conf.CONFIRMADO]} de {len(insumos)} confirmados"
                                 + (f" · {conteo[conf.REVISAR]} por revisar" if conteo[conf.REVISAR] else ""))

    def _fila(self, insumo, est, datos):
        fila = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(56), spacing=dp(8))
        detalle = f"{_pesos(insumo['precio'])} / «{insumo['unidad']}»"
        c = conf.confirmacion(insumo, datos)
        if c:
            detalle += f"  ·  precio por {_numero(c['contenido'])} {c['unidad_contenido']}, se mide en {c['unidad_base']}"
        lbl = MDLabel(
            text=f"[b]{insumo['nombre']}[/b]  [color={_hex(COLOR_ESTADO[est])}]{TEXTO_ESTADO[est]}[/color]\n{detalle}",
            markup=True, theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1))
        lbl.bind(texture_size=lambda _l, s: setattr(fila, "height", max(dp(56), s[1] + dp(8))))
        fila.add_widget(lbl)
        btn = MDIconButton(icon="check-circle-outline" if est == conf.CONFIRMADO else "scale-balance",
                           pos_hint={"center_y": 0.5})
        btn.bind(on_release=lambda *_: self.abrir(insumo))
        fila.add_widget(btn)
        return fila

    # ---------- diálogo de confirmación ----------

    def abrir(self, insumo):
        self._insumo = insumo
        self._usos = [(p["nombre"], ing["cantidad"]) for p in storage.get_platos()
                      for ing in p["ingredientes"] if ing["insumo_id"] == insumo["id"]]
        previa = conf.confirmacion(insumo)
        sug = conf.sugerir(insumo["unidad"])
        if previa:
            self._base, contenido = previa["unidad_base"], previa["contenido"]
            self._u_precio, self._u_receta = previa["unidad_contenido"], previa["unidad_receta"]
        elif sug:
            self._base, contenido = sug.unidad_base, str(sug.contenido)
            self._u_precio, self._u_receta = sug.unidad_contenido, sug.unidad_receta
        else:
            self._base, contenido, self._u_precio, self._u_receta = "g", "", "g", "g"

        caja = MDBoxLayout(orientation="vertical", spacing=dp(8), adaptive_height=True)
        usos = ", ".join(f"{n} ({_numero(c)})" for n, c in self._usos) or "ninguna receta"
        caja.add_widget(alto_segun_texto(MDLabel(
            text=f"Guardado hoy: [b]{_pesos(insumo['precio'])}[/b] por «{insumo['unidad']}», "
                 f"merma {_numero(Decimal(str(insumo['merma_pct'])) * 100)} %.\nSe usa en: {usos}.",
            markup=True)))
        if sug and not previa:
            caja.add_widget(alto_segun_texto(MDLabel(
                text="Sugerencia según el texto de la unidad: revísala antes de confirmar.",
                theme_text_color="Secondary", font_style="Body", role="small")))

        caja.add_widget(alto_segun_texto(MDLabel(text="1. ¿En qué se mide?", bold=True)))
        bases = MDBoxLayout(spacing=dp(6), size_hint_y=None, height=dp(44))
        self._btn_base = {}
        for b in conf.BASES:
            # Color del texto explícito: al pasar a "filled" KivyMD 2.0 no lo actualiza y queda invisible
            boton = MDButton(MDButtonText(text=b, theme_text_color="Custom"), style="outlined",
                             size_hint_y=None, height=dp(40))
            boton.bind(on_release=lambda _w, b=b: self._elegir_base(b))
            self._btn_base[b] = boton
            bases.add_widget(boton)
        caja.add_widget(bases)

        caja.add_widget(alto_segun_texto(MDLabel(
            text=f"2. ¿A cuánto corresponde el precio de {_pesos(insumo['precio'])}?", bold=True)))
        fila_precio = MDBoxLayout(spacing=dp(8), size_hint_y=None, height=dp(56))
        self.contenido_field = MDTextField(MDTextFieldHintText(text="Cantidad"), text=contenido, input_filter="float")
        self.contenido_field.bind(text=lambda *_: self._vista_previa())
        self.btn_u_precio = MDButton(MDButtonText(text=self._u_precio), style="tonal", size_hint_y=None, height=dp(48))
        self.btn_u_precio.bind(on_release=lambda w: self._menu_unidad(w, "_u_precio"))
        fila_precio.add_widget(self.contenido_field)
        fila_precio.add_widget(self.btn_u_precio)
        caja.add_widget(fila_precio)

        caja.add_widget(alto_segun_texto(MDLabel(text="3. En las recetas, las cantidades están en:", bold=True)))
        self.btn_u_receta = MDButton(MDButtonText(text=self._u_receta), style="tonal", size_hint_y=None, height=dp(48))
        self.btn_u_receta.bind(on_release=lambda w: self._menu_unidad(w, "_u_receta"))
        caja.add_widget(self.btn_u_receta)

        self.previa_lbl = alto_segun_texto(MDLabel(text="", markup=True))
        caja.add_widget(self.previa_lbl)
        self.error_lbl = alto_segun_texto(MDLabel(text="", theme_text_color="Custom",
                                                  text_color=(0.85, 0.25, 0.25, 1)))
        caja.add_widget(self.error_lbl)

        scroll = MDScrollView(size_hint_y=None, height=dp(420), do_scroll_x=False)
        scroll.add_widget(caja)

        botones = [MDButton(MDButtonText(text="CANCELAR"), style="text", on_release=lambda *_: self.dialog.dismiss())]
        if conf.estado(insumo) != conf.PENDIENTE:
            botones.append(MDButton(MDButtonText(text="QUITAR"), style="text", on_release=lambda *_: self._quitar()))
        botones.append(MDButton(MDButtonText(text="CONFIRMAR"), style="text", on_release=lambda *_: self._confirmar()))
        self.dialog = MDDialog(MDDialogHeadlineText(text=insumo["nombre"]), MDDialogContentContainer(scroll),
                               MDDialogButtonContainer(*botones))
        self._elegir_base(self._base)
        self.dialog.open()

    def _elegir_base(self, base):
        self._base = base
        for b, boton in self._btn_base.items():
            boton.style = "filled" if b == base else "outlined"
            texto = next(w for w in boton.walk() if isinstance(w, MDButtonText))
            texto.text_color = (1, 1, 1, 1) if b == base else COLOR_PRIMARIO
        # Al cambiar de dimensión, las unidades elegidas que ya no sirven vuelven a la base
        validas = unidades_de(base)
        if self._u_precio not in validas:
            self._u_precio = base
        if self._u_receta not in validas:
            self._u_receta = base
        set_texto_boton(self.btn_u_precio, self._u_precio)
        set_texto_boton(self.btn_u_receta, self._u_receta)
        self._vista_previa()

    def _menu_unidad(self, caller, atributo):
        def elegir(codigo):
            setattr(self, atributo, codigo)
            set_texto_boton(caller, codigo)
            self.menu.dismiss()
            self._vista_previa()

        items = [{"text": u, "on_release": lambda u=u: elegir(u)} for u in unidades_de(self._base)]
        self.menu = MDDropdownMenu(caller=caller, items=items, width=dp(160))
        self.menu.open()

    def _vista_previa(self):
        self.error_lbl.text = ""
        try:
            costo, filas = conf.impacto(self._insumo, self._usos, self._base, self.contenido_field.text or "0",
                                        self._u_precio, self._u_receta)
        except conf.ErrorConfirmacion as e:
            self.previa_lbl.text = ""
            if self.contenido_field.text:
                self.error_lbl.text = str(e)
            return
        lineas = [f"Costo por {self._base}: [b]{_pesos(costo, decimales=4)}[/b]"]
        for f in filas:
            cambio = "sin cambio" if f.costo_hoy == f.costo_interpretado else f"pasaría a {_pesos(f.costo_interpretado)}"
            lineas.append(f"• {f.plato}: hoy {_pesos(f.costo_hoy)}, {cambio}")
        if any(f.costo_hoy != f.costo_interpretado for f in filas):
            lineas.append("[color=#c0392b]El costo de estas recetas cambiaría al migrar. "
                          "Confirma solo si la interpretación es la correcta.[/color]")
        self.previa_lbl.text = "\n".join(lineas)

    def _confirmar(self):
        try:
            conf.confirmar(self._insumo, self._base, self.contenido_field.text, self._u_precio, self._u_receta)
        except conf.ErrorConfirmacion as e:
            self.error_lbl.text = str(e)
            return
        self.dialog.dismiss()
        self.refrescar()

    def _quitar(self):
        conf.quitar(self._insumo["id"])
        self.dialog.dismiss()
        self.refrescar()


def _hex(color):
    return "#" + "".join(f"{round(c * 255):02x}" for c in color[:3])
