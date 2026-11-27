"""Sistema visual del rediseño (prototipo aprobado el 2026-11-27): colores y piezas comunes."""
from decimal import Decimal

from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from views.utils import alto_segun_texto, set_texto_boton

FONDO = get_color_from_hex("#FAFAFA")
BLANCO = (1, 1, 1, 1)
BORDE = get_color_from_hex("#E4E4E7")
BORDE_SUAVE = get_color_from_hex("#F4F4F5")
TITULO = get_color_from_hex("#18181B")
TEXTO = get_color_from_hex("#52525B")
TEXTO_TENUE = get_color_from_hex("#71717A")
GRIS = get_color_from_hex("#A1A1AA")
GRIS_CLARO = get_color_from_hex("#D4D4D8")
ACENTO = get_color_from_hex("#0F766E")
ACENTO_FONDO = get_color_from_hex("#F0FDFA")
VERDE = get_color_from_hex("#15803D")
VERDE_FONDO = get_color_from_hex("#F0FDF4")
AMBAR = get_color_from_hex("#B45309")
AMBAR_FONDO = get_color_from_hex("#FFFBEB")
AMBAR_TEXTO = get_color_from_hex("#92400E")
ROJO = get_color_from_hex("#B91C1C")
ROJO_FONDO = get_color_from_hex("#FEF2F2")
NEGRO = get_color_from_hex("#18181B")

TONO = {
    "verde": (VERDE_FONDO, VERDE),
    "ambar": (AMBAR_FONDO, AMBAR_TEXTO),
    "rojo": (ROJO_FONDO, ROJO),
    "acento": (ACENTO_FONDO, ACENTO),
    "gris": (BORDE_SUAVE, TEXTO),
}

ESTILOS = {
    "titulo": ("Headline", "small"), "subtitulo": ("Title", "medium"), "cuerpo": ("Body", "medium"),
    "grande": ("Title", "large"), "pequeno": ("Body", "small"), "etiqueta": ("Label", "large"),
}


def pesos(valor):
    """$1.234 (CLP sin decimales, punto de miles); −$1.234 si es negativo."""
    v = int(Decimal(str(valor)).quantize(Decimal("1")))
    return ("−$" if v < 0 else "$") + f"{abs(v):,}".replace(",", ".")


def porcentaje(valor, decimales=1):
    v = Decimal(str(valor)).quantize(Decimal(1).scaleb(-decimales))
    texto = f"{abs(v):,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if v < 0 else "") + texto + " %"


def capitalizar(texto):
    texto = (texto or "").strip()
    return texto[:1].upper() + texto[1:]


def tono_margen(margen):
    return "verde" if margen >= 30 else "ambar" if margen >= 0 else "rojo"


def etiqueta(texto, estilo="cuerpo", color=TITULO, negrita=False, **kw):
    fuente, rol = ESTILOS[estilo]
    return alto_segun_texto(MDLabel(text=texto, font_style=fuente, role=rol, bold=negrita,
                                    theme_text_color="Custom", text_color=color, **kw))


def tarjeta(**kw):
    kw.setdefault("orientation", "vertical")
    t = MDCard(style="outlined", theme_bg_color="Custom", md_bg_color=BLANCO, theme_line_color="Custom",
               line_color=BORDE, radius=[dp(12)], size_hint_y=None, height=dp(60), **kw)
    t.bind(minimum_height=t.setter("height"))
    return t


def pildora(texto, tono):
    fondo, color = TONO[tono]
    caja = MDBoxLayout(adaptive_size=True, padding=(dp(8), dp(3)), md_bg_color=fondo, radius=[dp(10)])
    caja.add_widget(MDLabel(text=texto, adaptive_size=True, font_style="Label", role="large", bold=True,
                            theme_text_color="Custom", text_color=color))
    caja._texto = caja.children[0]
    return caja


def cambiar_pildora(caja, texto, tono):
    fondo, color = TONO[tono]
    caja.md_bg_color = fondo
    caja._texto.text = texto
    caja._texto.text_color = color


def boton(texto, al_tocar, tipo="borde", alto=dp(38), ancho=None):
    """tipo: 'primario' (relleno verde), 'borde' (blanco con borde) u 'oscuro' (segmento activo)."""
    txt = MDButtonText(text=texto, theme_text_color="Custom", bold=True,
                       pos_hint={"center_x": 0.5, "center_y": 0.5})
    b = MDButton(txt, style="filled", theme_bg_color="Custom", theme_width="Custom", theme_height="Custom",
                 theme_line_color="Custom", size_hint=(None if ancho else 1, None), height=alto, radius=[dp(8)])
    if ancho:
        b.width = ancho
    b._txt = txt
    b.bind(on_release=lambda *_: al_tocar())
    estilo_boton(b, tipo)
    return b


def estilo_boton(b, tipo):
    fondo, texto, borde = {
        "primario": (ACENTO, BLANCO, ACENTO),
        "borde": (BLANCO, get_color_from_hex("#3F3F46"), BORDE),
        "oscuro": (NEGRO, BLANCO, NEGRO),
        "plano": (BLANCO, TEXTO, BLANCO),
    }[tipo]
    b.md_bg_color, b._txt.text_color, b.line_color = fondo, texto, borde


class Segmentado(MDBoxLayout):
    """Grupo de opciones excluyentes (como 1x · 5x · 10x)."""

    def __init__(self, titulo, opciones, al_elegir, activo=None, **kw):
        super().__init__(adaptive_width=True, size_hint_y=None, height=dp(38), padding=dp(3), spacing=dp(2),
                         md_bg_color=BLANCO, radius=[dp(9)], **kw)
        self._al_elegir = al_elegir
        self.botones = {}
        if titulo:
            self.add_widget(MDLabel(text=titulo, adaptive_width=True, font_style="Body", role="small",
                                    theme_text_color="Custom", text_color=TEXTO_TENUE, padding=(dp(8), 0),
                                    pos_hint={"center_y": 0.5}))
        for clave, texto in opciones:
            b = boton(texto, lambda c=clave: self.elegir(c), tipo="plano", alto=dp(32), ancho=dp(12) + dp(8) * len(texto))
            b._txt.font_style, b._txt.role = "Label", "large"
            self.botones[clave] = b
            self.add_widget(b)
        self.marcar(activo)

    def marcar(self, activo):
        self.activo = activo
        for clave, b in self.botones.items():
            estilo_boton(b, "oscuro" if clave == activo else "plano")

    def elegir(self, clave):
        self.marcar(clave)
        self._al_elegir(clave)


def celda(contenido, ancho=None, alin="left", estilo="cuerpo", color=TITULO, negrita=False, markup=False):
    """Celda de tabla: texto o widget, con ancho fijo opcional."""
    if isinstance(contenido, str):
        fuente, rol = ESTILOS[estilo]
        w = MDLabel(text=contenido, font_style=fuente, role=rol, bold=negrita, halign=alin, markup=markup,
                    theme_text_color="Custom", text_color=color, size_hint_y=None)
        w.bind(texture_size=lambda l, t: setattr(l, "height", t[1]))
    else:
        w = contenido
    w.pos_hint = {"center_y": 0.5}
    if ancho:
        w.size_hint_x, w.width = None, ancho
    return w


def fila_tabla(celdas, al_tocar=None, alto_min=dp(44), relleno=dp(18)):
    f = MDCard(style="filled", theme_bg_color="Custom", md_bg_color=BLANCO, radius=[0], orientation="horizontal",
               padding=(relleno, dp(8)), spacing=dp(10), size_hint_y=None, height=alto_min,
               ripple_behavior=al_tocar is not None)
    for c in celdas:
        f.add_widget(c)
    f.bind(minimum_height=lambda w, h: setattr(w, "height", max(alto_min, h)))
    if al_tocar:
        f.bind(on_release=lambda *_: al_tocar())
    return f


def encabezado_tabla(columnas, relleno=dp(18)):
    """columnas: [(TEXTO, ancho o None, alineación)]."""
    caja = MDBoxLayout(size_hint_y=None, height=dp(34), padding=(relleno, 0), spacing=dp(10), md_bg_color=FONDO)
    for texto, ancho, alin in columnas:
        caja.add_widget(celda(texto, ancho, alin, "etiqueta", TEXTO_TENUE, negrita=True))
    return caja


def separador():
    return MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=BORDE_SUAVE)


__all__ = ["pesos", "porcentaje", "capitalizar", "tono_margen", "etiqueta", "tarjeta", "pildora",
           "cambiar_pildora", "boton", "estilo_boton", "Segmentado", "set_texto_boton", "celda", "fila_tabla",
           "encabezado_tabla", "separador"]
