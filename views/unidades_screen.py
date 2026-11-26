"""Confirmar, insumo por insumo, cómo se compra (D4/D6). Diseño del prototipo aprobado.

Dos pantallas:
- UnidadesScreen ("confirmar_unidades"): progreso, filtros y una tarjeta por insumo.
- ConfirmarInsumoScreen ("confirmar_insumo"): dos preguntas en lenguaje simple
  ("¿Qué compras por $X?" y "¿en qué se anota en tus recetas?") y el impacto en vivo.
  La unidad base sale sola de la unidad elegida (kg → g).

No modifica los insumos ni app.json: las decisiones van a models/confirmaciones.py.
"""
from decimal import Decimal, InvalidOperation

from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.card import MDCard
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDIcon, MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.progressindicator import MDLinearProgressIndicator
from kivymd.uix.screen import MDScreen
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText

from models import confirmaciones as conf, storage
from services.calculo_costos import UNIDADES
from views import marca
from views.utils import alto_segun_texto, set_texto_boton

LISTA, DETALLE = "confirmar_unidades", "confirmar_insumo"

FONDO = (0.957, 0.965, 0.965, 1)          # #f4f6f6
BLANCO = (1, 1, 1, 1)
BORDE = (0.882, 0.906, 0.906, 1)          # #e1e7e7
BORDE_CONTROL = (0.788, 0.831, 0.831, 1)  # #c9d4d4
TEXTO = (0.106, 0.141, 0.141, 1)          # #1b2424
TEXTO_SUAVE = (0.29, 0.345, 0.345, 1)     # #4a5858
ACENTO = marca.TURQUESA_OSCURO            # #0E7C7B, texto blanco encima 4,9:1
ACENTO_SUAVE = (0.89, 0.945, 0.945, 1)    # #e3f1f1

# (fondo, texto) de cada etiqueta de estado
PILDORA = {
    "sugerencia": ((0.89, 0.945, 0.945, 1), (0.043, 0.36, 0.36, 1)),
    "sin": ((1, 0.945, 0.86, 1), (0.54, 0.294, 0, 1)),
    "revisar": ((0.992, 0.91, 0.902, 1), (0.64, 0.149, 0.106, 1)),
    "listo": ((0.89, 0.953, 0.918, 1), (0.106, 0.42, 0.263, 1)),
}
AVISO = {
    "cambia": ((1, 0.945, 0.86, 1), (0.478, 0.259, 0, 1)),
    "igual": ((0.89, 0.953, 0.918, 1), (0.106, 0.42, 0.263, 1)),
    "neutro": (FONDO, TEXTO_SUAVE),
}
FILTROS = (("pendientes", "Pendientes"), ("revisar", "Revisar"), ("listos", "Listos"))
ESTADO_A_FILTRO = {conf.PENDIENTE: "pendientes", conf.REVISAR: "revisar", conf.CONFIRMADO: "listos"}


# ---------- utilidades de formato y widgets ----------

def pesos(valor, decimales=0):
    """$1.234 o $0,5 (formato chileno, sin ceros sobrantes)."""
    texto = f"{Decimal(str(valor)):,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if "," in texto:
        texto = texto.rstrip("0").rstrip(",")
    return "$" + texto


def numero(valor):
    return f"{Decimal(str(valor)).normalize():f}".replace(".", ",")


# Tamaños del prototipo → estilos tipográficos de KivyMD 2.0 (el tema ignora font_size)
ESTILO = {"26sp": ("Headline", "small"), "20sp": ("Title", "large"), "16sp": ("Title", "medium"),
          "15sp": ("Body", "large"), "14sp": ("Body", "medium"), "13sp": ("Body", "medium"),
          "12sp": ("Body", "small")}


def etiqueta(texto, tam="14sp", color=TEXTO, negrita=False, **kw):
    estilo, rol = ESTILO[tam]
    return alto_segun_texto(MDLabel(text=texto, font_style=estilo, role=rol, bold=negrita,
                                    theme_text_color="Custom", text_color=color, **kw))


def pildora(texto, tipo):
    fondo, color = PILDORA[tipo]
    caja = MDBoxLayout(adaptive_size=True, padding=(dp(8), dp(3)), md_bg_color=fondo, radius=[dp(10)])
    caja.add_widget(MDLabel(text=texto, adaptive_size=True, font_style="Label", role="large", bold=True,
                            theme_text_color="Custom", text_color=color))
    return caja


def boton(texto, al_tocar, relleno=False, alto=dp(48)):
    """Botón con colores explícitos (en KivyMD 2.0 el texto no se recolorea solo al cambiar de estilo)."""
    # pos_hint centra el texto cuando el botón es más ancho que él (theme_width="Custom")
    txt = MDButtonText(text=texto, theme_text_color="Custom", bold=True, pos_hint={"center_x": 0.5, "center_y": 0.5})
    b = MDButton(txt, style="filled", theme_bg_color="Custom", theme_width="Custom", theme_height="Custom",
                 size_hint=(1, None), height=alto, radius=[alto / 2])
    b.bind(on_release=lambda *_: al_tocar())
    b._txt = txt
    marcar_boton(b, relleno)
    return b


def marcar_boton(b, activo, deshabilitado=False):
    if deshabilitado:
        b.md_bg_color, b._txt.text_color = BORDE, TEXTO_SUAVE
    elif activo:
        b.md_bg_color, b._txt.text_color = ACENTO, BLANCO
    else:
        b.md_bg_color, b._txt.text_color = BLANCO, TEXTO
    b.theme_line_color = "Custom"
    b.line_color = ACENTO if activo and not deshabilitado else BORDE_CONTROL
    b.disabled = deshabilitado


def tarjeta(**kw):
    t = MDCard(style="outlined", theme_bg_color="Custom", md_bg_color=BLANCO, theme_line_color="Custom",
               line_color=BORDE, radius=[dp(14)], size_hint_y=None, height=dp(60), **kw)
    t.bind(minimum_height=t.setter("height"))  # alto inicial ≠ 0: ver views.utils.alto_segun_contenido
    return t


def cabecera(volver_texto, volver):
    """Franja blanca superior con el enlace para volver."""
    caja = MDBoxLayout(orientation="vertical", adaptive_height=True, padding=(dp(20), dp(8), dp(20), dp(14)),
                       spacing=dp(6), md_bg_color=BLANCO)
    atras = MDButton(MDButtonText(text=f"‹  {volver_texto}", theme_text_color="Custom", text_color=ACENTO),
                     style="text", size_hint_y=None, height=dp(44))
    atras.bind(on_release=lambda *_: volver())
    caja.add_widget(atras)
    return caja


# ---------- lista ----------

class UnidadesScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name=LISTA, md_bg_color=FONDO, **kwargs)
        self.filtro = "pendientes"
        raiz = MDBoxLayout(orientation="vertical")

        cab = cabecera("Mis Recetas", lambda: setattr(self.manager, "current", "mis_recetas"))
        cab.add_widget(etiqueta("Unidades de tus insumos", "26sp", negrita=True))
        cab.add_widget(etiqueta("Dinos cómo compras cada insumo para llevar inventario y cotizar con el "
                                "último precio. Tus recetas no cambian.", color=TEXTO_SUAVE))
        raiz.add_widget(cab)

        cuerpo = MDBoxLayout(orientation="vertical", padding=(dp(20), dp(16), dp(20), 0), spacing=dp(14))
        progreso = tarjeta(orientation="vertical", padding=dp(16), spacing=dp(10))
        fila = MDBoxLayout(adaptive_height=True)
        self.lbl_listos = etiqueta("", "16sp", negrita=True)
        self.lbl_faltan = etiqueta("", "13sp", TEXTO_SUAVE, halign="right")
        fila.add_widget(self.lbl_listos)
        fila.add_widget(self.lbl_faltan)
        progreso.add_widget(fila)
        self.barra = MDLinearProgressIndicator(size_hint_y=None, height=dp(8), value=0,
                                               indicator_color=ACENTO, track_color=BORDE)
        progreso.add_widget(self.barra)
        cuerpo.add_widget(progreso)

        filtros = MDBoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        self.btn_filtro = {}
        for clave, _texto in FILTROS:
            b = boton("", lambda c=clave: self._filtrar(c), alto=dp(40))
            b.size_hint_x = None
            b._txt.font_style, b._txt.role = "Label", "large"
            b._txt.bind(texture_size=lambda t, s, b=b: setattr(b, "width", s[0] + dp(24)))
            self.btn_filtro[clave] = b
            filtros.add_widget(b)
        filtros.add_widget(Widget())
        cuerpo.add_widget(filtros)

        scroll = MDScrollView(do_scroll_x=False)
        self.lista = MDBoxLayout(orientation="vertical", spacing=dp(10), adaptive_height=True,
                                 padding=(0, 0, 0, dp(20)))
        scroll.add_widget(self.lista)
        cuerpo.add_widget(scroll)
        raiz.add_widget(cuerpo)
        self.add_widget(raiz)

    def on_pre_enter(self, *args):
        self.refrescar()

    def _filtrar(self, clave):
        self.filtro = clave
        self.refrescar()

    def refrescar(self):
        self.lista.clear_widgets()
        try:
            datos = conf.cargar()
        except conf.ErrorConfirmacion as e:
            self.lbl_listos.text, self.lbl_faltan.text = str(e), ""
            return
        insumos = storage.get_insumos()
        grupos = {"pendientes": [], "revisar": [], "listos": []}
        for i in insumos:
            grupos[ESTADO_A_FILTRO[conf.estado(i, datos)]].append(i)
        listos, total = len(grupos["listos"]), len(insumos)
        self.lbl_listos.text = f"{listos} de {total} listos"
        self.lbl_faltan.text = f"{total - listos} por confirmar"
        self.barra.value = 100 * listos / total if total else 0
        for clave, texto in FILTROS:
            set_texto_boton(self.btn_filtro[clave], f"{texto} ({len(grupos[clave])})")
            marcar_boton(self.btn_filtro[clave], clave == self.filtro)
        for insumo in grupos[self.filtro]:
            self.lista.add_widget(self._tarjeta(insumo, datos))
        if not grupos[self.filtro]:
            self.lista.add_widget(etiqueta("No hay insumos en este grupo.", color=TEXTO_SUAVE, halign="center"))

    def _tarjeta(self, insumo, datos):
        est = conf.estado(insumo, datos)
        if est == conf.CONFIRMADO:
            c = conf.confirmacion(insumo, datos)
            pill = (f"Listo · {conf.cantidad_texto(c['contenido'], c['unidad_contenido'])}", "listo")
        elif est == conf.REVISAR:
            pill = ("Cambió el nombre o la unidad: revisar", "revisar")
        else:
            ops, sugerida = conf.opciones_compra(insumo)
            pill = ((f"Sugerencia: {conf.cantidad_texto(*ops[0][:2])}", "sugerencia") if sugerida
                    else ("Sin sugerencia: necesita tu ayuda", "sin"))
        t = tarjeta(orientation="horizontal", padding=(dp(16), dp(12), dp(10), dp(12)), spacing=dp(10))
        t.bind(on_release=lambda *_: self._abrir(insumo))
        textos = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(4))
        textos.add_widget(etiqueta(insumo["nombre"], "16sp", negrita=True))
        textos.add_widget(etiqueta(f"{pesos(insumo['precio'])} por «{insumo['unidad']}»", "13sp", TEXTO_SUAVE))
        textos.add_widget(pildora(*pill))
        t.add_widget(textos)
        t.add_widget(MDIcon(icon="chevron-right", theme_text_color="Custom", text_color=TEXTO_SUAVE,
                            pos_hint={"center_y": 0.5}, size_hint_x=None, width=dp(24)))
        return t

    def _abrir(self, insumo):
        self.manager.get_screen(DETALLE).cargar(insumo)
        self.manager.current = DETALLE


# ---------- confirmar un insumo ----------

class ConfirmarInsumoScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name=DETALLE, md_bg_color=FONDO, **kwargs)
        self.menu = None
        raiz = MDBoxLayout(orientation="vertical")
        cab = cabecera("Unidades", self._volver)
        self.fila_titulo = MDBoxLayout(adaptive_height=True, spacing=dp(10))
        cab.add_widget(self.fila_titulo)
        self.lbl_hoy = etiqueta("", color=TEXTO_SUAVE, markup=True)
        cab.add_widget(self.lbl_hoy)
        raiz.add_widget(cab)

        scroll = MDScrollView(do_scroll_x=False)
        self.cuerpo = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(14),
                                  padding=(dp(20), dp(16), dp(20), dp(20)))
        scroll.add_widget(self.cuerpo)
        raiz.add_widget(scroll)

        pie = MDBoxLayout(size_hint_y=None, height=dp(80), padding=(dp(20), dp(12), dp(20), dp(20)),
                          spacing=dp(10), md_bg_color=BLANCO)
        self.btn_despues = boton("Después", self._volver)
        self.btn_confirmar = boton("Confirmar", self._confirmar, relleno=True)
        self.btn_despues.size_hint_x, self.btn_confirmar.size_hint_x = 1, 2
        pie.add_widget(self.btn_despues)
        pie.add_widget(self.btn_confirmar)
        raiz.add_widget(pie)
        self.add_widget(raiz)

    def _volver(self):
        self.manager.current = LISTA

    # --- armado ---

    def cargar(self, insumo):
        self.insumo = insumo
        self.usos = [(p["nombre"], ing["cantidad"]) for p in storage.get_platos()
                     for ing in p["ingredientes"] if ing["insumo_id"] == insumo["id"]]
        self.opciones, sugerida = conf.opciones_compra(insumo)
        previa = conf.confirmacion(insumo)
        est = conf.estado(insumo)
        self.eleccion, self.otra_cantidad, self.otra_unidad = None, "", "kg"
        self.receta = None
        if previa:
            par = (Decimal(previa["contenido"]), previa["unidad_contenido"])
            idx = next((k for k, o in enumerate(self.opciones) if (o[0], o[1]) == par), None)
            if idx is None:
                self.eleccion, self.otra_cantidad, self.otra_unidad = "otra", previa["contenido"], par[1]
            else:
                self.eleccion = idx
            self.receta = previa["unidad_receta"]
        elif sugerida:
            self.eleccion, self.receta = 0, self.opciones[0][1]

        self.fila_titulo.clear_widgets()
        self.fila_titulo.add_widget(MDLabel(text=insumo["nombre"], font_style="Headline", role="small", bold=True,
                                            adaptive_size=True, theme_text_color="Custom", text_color=TEXTO))
        tipo = {conf.CONFIRMADO: ("Listo", "listo"), conf.REVISAR: ("Por revisar", "revisar")}.get(
            est, ("Por confirmar", "sugerencia") if sugerida else ("Sin sugerencia", "sin"))
        pill = pildora(*tipo)
        pill.pos_hint = {"center_y": 0.5}
        self.fila_titulo.add_widget(pill)
        merma = f"{Decimal(str(insumo['merma_pct'])) * 100:.0f}"
        recetas = f"en {len(self.usos)} receta{'s' if len(self.usos) != 1 else ''}"
        self.lbl_hoy.text = (f"Hoy: [b]{pesos(insumo['precio'])}[/b] por «{insumo['unidad']}» · "
                             f"merma {merma} % · {recetas}")
        self._armar_cuerpo(sugerida, est != conf.PENDIENTE)
        self._actualizar()

    def _armar_cuerpo(self, sugerida, hay_previa):
        c = self.cuerpo
        c.clear_widgets()
        if not sugerida:
            aviso = tarjeta(orientation="horizontal", padding=(dp(14), dp(12)), spacing=dp(10))
            aviso.add_widget(MDIcon(icon="alert-circle-outline", theme_text_color="Custom",
                                    text_color=PILDORA["sin"][1], size_hint_x=None, width=dp(24)))
            aviso.add_widget(etiqueta(f"«{self.insumo['unidad']}» no dice cuánto compras. Elige una opción o "
                                      "escribe la cantidad.", "13sp", TEXTO_SUAVE))
            c.add_widget(aviso)

        c.add_widget(etiqueta(f"¿Qué compras por {pesos(self.insumo['precio'])}?", "16sp", negrita=True))
        self.tarjetas_opcion = []
        for k, (cant, uni, detalle) in enumerate(self.opciones):
            self.tarjetas_opcion.append(self._opcion(k, conf.cantidad_texto(cant, uni)))
        self.tarjetas_opcion.append(self._opcion("otra", "Otra cantidad"))
        for t in self.tarjetas_opcion:
            c.add_widget(t)

        self.fila_otra = MDBoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        self.campo_otra = MDTextField(MDTextFieldHintText(text="Cantidad"), mode="outlined",
                                      input_filter="float", text=str(self.otra_cantidad))
        self.campo_otra.bind(text=lambda *_: self._cambio_otra())
        self.btn_otra_unidad = boton(conf.NOMBRES[self.otra_unidad], self._menu_otra, alto=dp(48))
        self.btn_otra_unidad.size_hint_x = None
        self.btn_otra_unidad.width = dp(150)
        self.fila_otra.add_widget(self.campo_otra)
        self.fila_otra.add_widget(self.btn_otra_unidad)
        self.cont_otra = MDBoxLayout(orientation="vertical", adaptive_height=True)
        c.add_widget(self.cont_otra)

        c.add_widget(Widget(size_hint_y=None, height=dp(4)))
        self.lbl_receta = etiqueta("", "16sp", negrita=True)
        self.grilla_receta = MDGridLayout(cols=2, spacing=dp(8), adaptive_height=True)
        self.lbl_ejemplo = etiqueta("", "12sp", TEXTO_SUAVE)
        self.impacto = tarjeta(orientation="vertical", padding=(dp(16), dp(14)), spacing=dp(10))
        for w in (self.lbl_receta, self.grilla_receta, self.lbl_ejemplo, self.impacto):
            c.add_widget(w)
        if hay_previa:
            quitar = MDButton(MDButtonText(text="Quitar confirmación", theme_text_color="Custom",
                                           text_color=PILDORA["revisar"][1]), style="text",
                              pos_hint={"center_x": 0.5})
            quitar.bind(on_release=lambda *_: self._quitar())
            c.add_widget(quitar)

    def _opcion(self, clave, titulo):
        t = tarjeta(orientation="horizontal", padding=(dp(14), dp(10)), spacing=dp(12))
        t.bind(on_release=lambda *_: self._elegir(clave))
        t._icono = MDIcon(icon="radiobox-blank", theme_text_color="Custom", size_hint_x=None, width=dp(24),
                          pos_hint={"center_y": 0.5})
        textos = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(2),
                             pos_hint={"center_y": 0.5})
        textos.add_widget(etiqueta(titulo, "15sp", negrita=True))
        t._detalle = etiqueta("La escribes tú" if clave == "otra" else "", "12sp", TEXTO_SUAVE)
        textos.add_widget(t._detalle)
        t.add_widget(t._icono)
        t.add_widget(textos)
        t._clave = clave
        if isinstance(clave, int):
            cant, uni, detalle = self.opciones[clave]
            costo = Decimal(str(self.insumo["precio"])) / (cant * UNIDADES[uni][2])
            extra = f"{pesos(costo, 4)} por {conf.SINGULAR_BASE[conf.base_de(uni)]}"
            t._detalle.text = f"{detalle} · {extra}" if detalle else extra
        return t

    # --- interacción ---

    def _elegir(self, clave):
        self.eleccion = clave
        self._actualizar()

    def _cambio_otra(self):
        self.otra_cantidad = self.campo_otra.text
        self._actualizar()

    def _menu_otra(self):
        def elegir(u):
            self.otra_unidad = u
            set_texto_boton(self.btn_otra_unidad, conf.NOMBRES[u])
            self.menu.dismiss()
            self._actualizar()
        items = [{"text": conf.NOMBRES[u], "on_release": lambda u=u: elegir(u)} for u in conf.NOMBRES]
        self.menu = MDDropdownMenu(caller=self.btn_otra_unidad, items=items, width=dp(200))
        self.menu.open()

    def _elegir_receta(self, u):
        self.receta = u
        self._actualizar()

    def _compra(self):
        """(contenido, unidad) elegidos, o None si falta."""
        if self.eleccion is None:
            return None
        if self.eleccion == "otra":
            try:
                n = Decimal(str(self.otra_cantidad).replace(",", "."))
            except InvalidOperation:
                return None
            return (n, self.otra_unidad) if n.is_finite() and n > 0 else None
        cant, uni, _ = self.opciones[self.eleccion]
        return cant, uni

    def _actualizar(self):
        for t in self.tarjetas_opcion:
            activa = t._clave == self.eleccion
            t.md_bg_color = ACENTO_SUAVE if activa else BLANCO
            t.line_color = ACENTO if activa else BORDE_CONTROL
            t._icono.icon = "radiobox-marked" if activa else "radiobox-blank"
            t._icono.text_color = ACENTO if activa else TEXTO_SUAVE
        self.cont_otra.clear_widgets()
        if self.eleccion == "otra":
            self.cont_otra.add_widget(self.fila_otra)

        compra = self._compra()
        self.lbl_receta.text = f"En tus recetas, «{self.insumo['nombre'].lower()}» se anota en…"
        self.grilla_receta.clear_widgets()
        if compra:
            base = conf.base_de(compra[1])
            unidades_receta = conf.UNIDADES_RECETA[base]
            if self.receta not in unidades_receta:
                self.receta = compra[1] if compra[1] in unidades_receta else base
            for u in unidades_receta:
                b = boton(conf.NOMBRES[u], lambda u=u: self._elegir_receta(u))
                marcar_boton(b, u == self.receta)
                self.grilla_receta.add_widget(b)
        else:
            self.grilla_receta.add_widget(etiqueta("Primero elige qué compras.", "13sp", TEXTO_SUAVE))
        if self.usos:
            plato, cant = self.usos[0]
            self.lbl_ejemplo.text = f"Ejemplo de tu receta: {plato} usa «{numero(cant)}»."
        else:
            self.lbl_ejemplo.text = "Este insumo todavía no está en ninguna receta."
        self._impacto(compra)

    def _impacto(self, compra):
        im = self.impacto
        im.clear_widgets()
        if not compra:
            im.add_widget(etiqueta("Elige qué compras para ver cómo cambia el costo de tus recetas.",
                                   "13sp", TEXTO_SUAVE))
            marcar_boton(self.btn_confirmar, True, deshabilitado=True)
            return
        base = conf.base_de(compra[1])
        try:
            costo, filas = conf.impacto(self.insumo, self.usos, base, compra[0], compra[1], self.receta)
        except conf.ErrorConfirmacion as e:
            im.add_widget(etiqueta(str(e), "13sp", PILDORA["revisar"][1]))
            marcar_boton(self.btn_confirmar, True, deshabilitado=True)
            return
        fila = MDBoxLayout(adaptive_height=True)
        fila.add_widget(etiqueta(f"Costo por {conf.SINGULAR_BASE[base]}", "13sp", TEXTO_SUAVE))
        fila.add_widget(etiqueta(pesos(costo, 4), "20sp", negrita=True, halign="right"))
        im.add_widget(fila)
        im.add_widget(Widget(size_hint_y=None, height=dp(1)))
        cambian = [f for f in filas if f.costo_hoy != f.costo_interpretado]
        for f in filas:
            r = MDBoxLayout(adaptive_height=True, spacing=dp(8))
            r.add_widget(etiqueta(f.plato))
            r.add_widget(etiqueta(f"{pesos(f.costo_hoy)} pasa a [b]{pesos(f.costo_interpretado)}[/b]"
                                  if f in cambian else f"{pesos(f.costo_hoy)}, sin cambio",
                                  color=TEXTO_SUAVE, halign="right", markup=True))
            im.add_widget(r)
        if cambian:
            tipo = "cambia"
            texto = ("El costo de " + ", ".join(f.plato for f in cambian[:3])
                     + (" y otras" if len(cambian) > 3 else "")
                     + " cambiaría. Confirma solo si así es como compras y anotas este insumo.")
        elif filas:
            tipo, texto = "igual", "Tus recetas mantienen su costo."
        else:
            tipo, texto = "neutro", "No afecta a ninguna receta todavía."
        fondo, color = AVISO[tipo]
        caja = MDBoxLayout(adaptive_height=True, padding=(dp(12), dp(10)), md_bg_color=fondo, radius=[dp(10)])
        caja.add_widget(etiqueta(texto, "13sp", color))
        im.add_widget(caja)
        marcar_boton(self.btn_confirmar, True)

    def _confirmar(self):
        compra = self._compra()
        if not compra:
            return
        try:
            conf.confirmar(self.insumo, conf.base_de(compra[1]), compra[0], compra[1], self.receta)
        except conf.ErrorConfirmacion:
            return
        self._volver()

    def _quitar(self):
        conf.quitar(self.insumo["id"])
        self._volver()
