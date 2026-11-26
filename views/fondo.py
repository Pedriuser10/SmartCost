"""Fondo claro con puntos, común a las pantallas con el estilo nuevo (inicio de sesión e inicio)."""
from kivy.graphics import Color, Rectangle
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex

FONDO = get_color_from_hex("#FAFBFC")
PUNTO = (211, 219, 227)                  # #d3dbe3
PASO_PUNTOS = 20                         # separación de los puntos (dp)


def _textura_puntos(paso, radio):
    """Mosaico de paso×paso píxeles con un punto suave al centro; se repite en todo el fondo."""
    buf = bytearray(paso * paso * 4)
    centro = paso / 2
    for y in range(paso):
        for x in range(paso):
            distancia = ((x + 0.5 - centro) ** 2 + (y + 0.5 - centro) ** 2) ** 0.5
            alfa = max(0.0, min(1.0, radio + 0.5 - distancia))
            if alfa:
                i = (y * paso + x) * 4
                buf[i:i + 4] = bytes((*PUNTO, int(255 * alfa)))
    textura = Texture.create(size=(paso, paso), colorfmt="rgba")
    textura.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
    textura.wrap = "repeat"
    return textura


class FondoPuntos(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._paso = max(8, int(dp(PASO_PUNTOS)))
        with self.canvas:
            Color(*FONDO)
            self._fondo = Rectangle()
            Color(1, 1, 1, 1)
            self._puntos = Rectangle(texture=_textura_puntos(self._paso, max(1.0, dp(1))))
        self.bind(pos=self._dibujar, size=self._dibujar)

    def _dibujar(self, *args):
        for r in (self._fondo, self._puntos):
            r.pos, r.size = self.pos, self.size
        u, v = self.width / self._paso, self.height / self._paso
        self._puntos.tex_coords = (0, 0, u, 0, u, v, 0, v)
