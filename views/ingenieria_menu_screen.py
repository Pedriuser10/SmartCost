"""Pantalla 'Ingeniería de Menú': ranking de rentabilidad de todos los platos."""
from kivy.metrics import dp, sp
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle, Line, PushMatrix, PopMatrix, Rotate
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDButton, MDButtonText
from models import storage
from services.calculo_costos import costo_real_plato, margen, COLOR_MARGEN, clasificar_margen
from kivymd.uix.fitimage import FitImage
from views.utils import alto_segun_texto, alto_segun_contenido


class GraficoBarras(Widget):
    """Gráfico de barras dibujado con el canvas de Kivy (sin matplotlib ni archivos PNG)."""

    TEXTO = (0.2, 0.2, 0.2, 1)
    EJE = (0.6, 0.6, 0.6, 1)
    GUIA = (0.9, 0.9, 0.9, 1)

    def __init__(self, nombres, valores, titulo, etiqueta_y, color="#4CAF50", **kwargs):
        super().__init__(**kwargs)
        self.nombres = nombres
        self.valores = valores
        self.titulo = titulo
        self.etiqueta_y = etiqueta_y
        self.color_barra = get_color_from_hex(color)
        self.bind(pos=self._dibujar, size=self._dibujar)

    @staticmethod
    def _textura(texto, tamano, bold=False):
        etiqueta = CoreLabel(text=texto, font_size=tamano, bold=bold, color=GraficoBarras.TEXTO)
        etiqueta.refresh()
        return etiqueta.texture

    def _texto(self, texto, tamano, centro_x, y, bold=False):
        tex = self._textura(texto, tamano, bold)
        Rectangle(texture=tex, size=tex.size, pos=(centro_x - tex.width / 2, y))

    def _dibujar(self, *args):
        self.canvas.clear()
        if not self.valores or self.width < dp(80) or self.height < dp(80):
            return

        # Márgenes del área de barras: título arriba, nombres abajo, escala a la izquierda
        izq, der, abajo, arriba = dp(56), dp(8), dp(24), dp(28)
        x0, y0 = self.x + izq, self.y + abajo
        ancho, alto = self.width - izq - der, self.height - abajo - arriba

        # El rango siempre incluye el 0, así los márgenes negativos bajan del eje
        v_max, v_min = max(max(self.valores), 0), min(min(self.valores), 0)
        if v_max == v_min:
            v_max = v_min + 1

        def y_de(valor):
            return y0 + (valor - v_min) / (v_max - v_min) * alto

        with self.canvas:
            # Título
            Color(1, 1, 1, 1)
            self._texto(self.titulo, sp(14), self.x + self.width / 2, self.top - arriba + dp(4), bold=True)

            # Escala: líneas guía con su valor a la izquierda
            y_ultima_etiqueta = None
            for valor in sorted({v_min, 0, v_max}, key=lambda v: (v != 0, v)):  # el 0 primero: siempre se rotula
                y = y_de(valor)
                Color(*(self.EJE if valor == 0 else self.GUIA))
                Line(points=[x0, y, x0 + ancho, y], width=1)
                tex = self._textura(f"{valor:.0f}", sp(10))
                # Si dos valores quedan muy juntos (p. ej. 41 y 0) se omite el rótulo para no encimarlos
                if y_ultima_etiqueta is not None and abs(y - y_ultima_etiqueta) < tex.height:
                    continue
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, size=tex.size, pos=(x0 - tex.width - dp(4), y - tex.height / 2))
                y_ultima_etiqueta = y

            # Etiqueta del eje Y, rotada 90°
            tex = self._textura(self.etiqueta_y, sp(11))
            cx, cy = self.x + dp(10), y0 + alto / 2
            PushMatrix()
            Rotate(angle=90, origin=(cx, cy))
            Rectangle(texture=tex, size=tex.size, pos=(cx - tex.width / 2, cy - tex.height / 2))
            PopMatrix()

            # Barras (80% del espacio de cada plato) y nombre debajo
            espacio = ancho / len(self.valores)
            ancho_barra = espacio * 0.8
            max_chars = max(3, int(espacio / (sp(10) * 0.55)))
            for i, (nombre, valor) in enumerate(zip(self.nombres, self.valores)):
                bx = x0 + i * espacio + (espacio - ancho_barra) / 2
                y_cero, y_valor = y_de(0), y_de(valor)
                Color(*self.color_barra)
                Rectangle(pos=(bx, min(y_cero, y_valor)), size=(ancho_barra, abs(y_valor - y_cero)))

                Color(1, 1, 1, 1)
                corto = nombre if len(nombre) <= max_chars else nombre[:max_chars - 1] + "…"
                self._texto(corto, sp(10), bx + ancho_barra / 2, self.y + dp(4))


class IngenieriaMenuScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="ingenieria_de_menu", md_bg_color=(0.95, 0.95, 0.95, 1), **kwargs)
        root = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(16))
        back = MDButton(MDButtonText(text="‹  Volver al inicio"), style="text", size_hint_y=None, height=dp(48))
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "inicio"))
        root.add_widget(back)
        root.add_widget(MDLabel(text="Ingeniería de Menú", font_style="Headline", role="medium", bold=True, size_hint_y=None, height=dp(52), theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1)))
        self.resumen_label = MDLabel(text="", theme_text_color="Secondary", size_hint_y=None, height=dp(30))
        root.add_widget(self.resumen_label)
        scroll = MDScrollView()
        self.container = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        self.container.bind(minimum_height=self.container.setter("height"))
        scroll.add_widget(self.container)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_pre_enter(self, *args):
        self.refrescar()

    def refrescar(self):
        self.container.clear_widgets()
        resultados = []
        for plato in storage.get_platos():
            usados = storage.get_insumos_de_plato(plato["id"])
            costo = costo_real_plato(usados, plato["mano_obra"])
            m = margen(plato["precio_venta"], costo)
            resultados.append({"nombre": plato["nombre"], "precio_venta": plato["precio_venta"], "costo": costo, "margen": m, "categoria": clasificar_margen(m)})

        resultados.sort(key=lambda r: r["margen"], reverse=True)

        if resultados:
            promedio = sum(r["margen"] for r in resultados) / len(resultados)
            self.resumen_label.text = f"Margen promedio del menú: {promedio:.1f}%"
            nombres = [r["nombre"] for r in resultados]
            margenes = [r["margen"] for r in resultados]

            grafico_card = MDCard(size_hint_y=None, height=dp(260), radius=[dp(10)], padding=dp(8), theme_bg_color="Custom", md_bg_color=(1, 1, 1, 1))
            grafico_card.add_widget(GraficoBarras(nombres, margenes, "Rentabilidad por Plato (%)", "Margen", color="#4CAF50"))
            self.container.add_widget(grafico_card)
        else:
            self.resumen_label.text = "Aún no hay platos cargados. Créalos en 'Mis Recetas'."
        for r in resultados:
            card = MDCard(orientation="vertical", size_hint_y=None, height=dp(90), padding=dp(12), spacing=dp(4), theme_bg_color="Custom", md_bg_color=COLOR_MARGEN[r["categoria"]], radius=[dp(10)])
            card.add_widget(alto_segun_texto(MDLabel(text=r["nombre"], bold=True, font_style="Title", role="medium", theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1)), dp(24)))
            card.add_widget(alto_segun_texto(MDLabel(text=f"Venta ${r['precio_venta']:,.0f}  ·  Costo real ${r['costo']:,.0f}  ·  Margen {r['margen']:.1f}%", theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1)), dp(24)))
            self.container.add_widget(alto_segun_contenido(card))