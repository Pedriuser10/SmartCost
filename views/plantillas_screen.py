"""
Pantalla 'Mis Plantillas':
1) Generador de combinaciones: arma un plato eligiendo proteína + guarnición + salsa.
2) Importador CSV: carga muchas recetas propias de una vez desde un archivo.
3) Accesos rápidos: un puñado de recetas típicas listas con un toque.
"""
import csv
import os
from collections import OrderedDict

from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField , MDTextFieldHintText
from kivymd.uix.card import MDCard
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.filemanager import MDFileManager
from models import storage
from services.calculo_costos import costo_real_plato, margen
from services.plantillas import PLANTILLAS
from services.combinaciones import PROTEINAS, GUARNICIONES, SALSAS
from kivymd.uix.button import MDButton, MDButtonText
from views.utils import set_texto_boton

def _crear_plato_con_insumos(nombre, precio_venta, mano_obra, lista_insumos):
    """
    lista_insumos: [{"nombre","unidad","precio","merma_pct","cantidad"}, ...]
    Crea los insumos que falten, el plato, y la receta completa.
    """
    insumos_existentes = {i["nombre"].lower(): i for i in storage.get_insumos()}
    ids_por_nombre = {}

    for ins in lista_insumos:
        if ins["cantidad"] <= 0:
            continue  # ej. "Sin salsa"
        clave = ins["nombre"].lower()
        if clave in insumos_existentes:
            ids_por_nombre[clave] = insumos_existentes[clave]["id"]
        else:
            storage.add_insumo(ins["nombre"], ins["unidad"], ins["precio"], ins["merma_pct"] / 100)
            nuevo = next(i for i in storage.get_insumos() if i["nombre"].lower() == clave)
            ids_por_nombre[clave] = nuevo["id"]
            insumos_existentes[clave] = nuevo

    plato_id = storage.add_plato(nombre, precio_venta, mano_obra)
    for ins in lista_insumos:
        if ins["cantidad"] <= 0:
            continue
        storage.add_insumo_a_plato(plato_id, ids_por_nombre[ins["nombre"].lower()], ins["cantidad"])
    return plato_id


class PlantillasScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="mis_plantillas", md_bg_color=(0.95, 0.95, 0.95, 1), **kwargs)
        self.menu = None
        self.file_manager = None
        self._proteina = None
        self._guarnicion = None
        self._salsa = SALSAS[0]  # "Sin salsa" por defecto

        root = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(14))

        back = MDButton(MDButtonText(text="‹  Volver al inicio"), style="text", size_hint_y=None, height=dp(48))
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "inicio"))
        root.add_widget(back)

        root.add_widget(
            MDLabel(text="Mis Plantillas", font_style="Headline", role="medium", bold=True, size_hint_y=None, height=dp(52),
                    theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1))
        )

        self.estado_label = MDLabel(
            text="", size_hint_y=None, height=dp(30),
            theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1),
        )
        root.add_widget(self.estado_label)

        scroll = MDScrollView()
        contenido = MDBoxLayout(orientation="vertical", spacing=dp(20), size_hint_y=None, padding=(0, dp(6)))
        contenido.bind(minimum_height=contenido.setter("height"))

        contenido.add_widget(self._seccion_generador())
        contenido.add_widget(self._seccion_importar_csv())
        contenido.add_widget(self._seccion_accesos_rapidos())

        scroll.add_widget(contenido)
        root.add_widget(scroll)

        self.add_widget(root)

    # ---------- Sección 1: generador de combinaciones ----------

    def _seccion_generador(self):
        card = MDCard(
            orientation="vertical", size_hint_y=None, height=dp(350),
            padding=dp(16), spacing=dp(10), theme_bg_color="Custom", md_bg_color=(1, 1, 1, 1), radius=[dp(10)],
        )
        card.add_widget(MDLabel(
            text="Generador de combinaciones", bold=True, font_style="Title", role="large",
            theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1), size_hint_y=None, height=dp(30),
        ))
        card.add_widget(MDLabel(
            text=f"{len(PROTEINAS)} proteínas × {len(GUARNICIONES)} guarniciones × {len(SALSAS)} salsas "
                 f"= {len(PROTEINAS) * len(GUARNICIONES) * len(SALSAS)} platos posibles.",
            theme_text_color="Secondary", size_hint_y=None, height=dp(24),
        ))

        selectores = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.btn_proteina = MDButton(MDButtonText(text="Proteína"), style="outlined", size_hint_y=None, height=dp(48))
        self.btn_guarnicion = MDButton(MDButtonText(text="Guarnición"), style="outlined", size_hint_y=None, height=dp(48))
        self.btn_salsa = MDButton(MDButtonText(text="Salsa (opcional)"), style="outlined", size_hint_y=None, height=dp(48))
        self.btn_proteina.bind(on_release=lambda b: self._abrir_selector(b, PROTEINAS, self._set_proteina))
        self.btn_guarnicion.bind(on_release=lambda b: self._abrir_selector(b, GUARNICIONES, self._set_guarnicion))
        self.btn_salsa.bind(on_release=lambda b: self._abrir_selector(b, SALSAS, self._set_salsa))
        selectores.add_widget(self.btn_proteina)
        selectores.add_widget(self.btn_guarnicion)
        selectores.add_widget(self.btn_salsa)
        card.add_widget(selectores)

        self.nombre_combo_field = MDTextField(MDTextFieldHintText(text="Nombre del plato (se sugiere solo)"))
        self.precio_combo_field = MDTextField(MDTextFieldHintText(text="Precio de venta"), input_filter="float")
        card.add_widget(self.nombre_combo_field)
        card.add_widget(self.precio_combo_field)

        crear_btn = MDButton(MDButtonText(text="CREAR PLATO CON ESTA COMBINACIÓN"), style="filled", size_hint_y=None, height=dp(48))
        crear_btn.bind(on_release=lambda x: self._crear_combo())
        card.add_widget(crear_btn)
        return card

    def _abrir_selector(self, boton, lista, callback):
        items = [{"text": item["nombre"], "on_release": lambda i=item: callback(i)} for item in lista]
        self.menu = MDDropdownMenu(caller=boton, items=items, width_mult=4)
        self.menu.open()

    def _set_proteina(self, item):
        self._proteina = item
        set_texto_boton(self.btn_proteina, item["nombre"])
        self.menu.dismiss()
        self._sugerir_nombre()

    def _set_guarnicion(self, item):
        self._guarnicion = item
        set_texto_boton(self.btn_guarnicion, item["nombre"])
        self.menu.dismiss()
        self._sugerir_nombre()

    def _set_salsa(self, item):
        self._salsa = item
        set_texto_boton(self.btn_salsa, item["nombre"])
        self.menu.dismiss()
        self._sugerir_nombre()

    def _sugerir_nombre(self):
        if not (self._proteina and self._guarnicion):
            return
        nombre = f"{self._proteina['nombre']} con {self._guarnicion['nombre']}"
        if self._salsa and self._salsa["nombre"] != "Sin salsa":
            nombre += f" y {self._salsa['nombre']}"
        self.nombre_combo_field.text = nombre

    def _crear_combo(self):
        if not (self._proteina and self._guarnicion):
            self.estado_label.text_color = (0.9, 0.3, 0.3, 1)
            self.estado_label.text = "⚠ Elige al menos proteína y guarnición."
            return
        nombre = self.nombre_combo_field.text.strip()
        try:
            precio_venta = float(self.precio_combo_field.text or 0)
        except ValueError:
            precio_venta = 0
        if not nombre or precio_venta <= 0:
            self.estado_label.text_color = (0.9, 0.3, 0.3, 1)
            self.estado_label.text = "⚠ Falta el nombre o un precio de venta válido."
            return

        insumos = [self._proteina, self._guarnicion]
        if self._salsa:
            insumos.append(self._salsa)

        _crear_plato_con_insumos(nombre, precio_venta, mano_obra=400, lista_insumos=insumos)

        self.estado_label.text_color = (0.2, 0.8, 0.4, 1)
        self.estado_label.text = f"✓ '{nombre}' se creó con su receta. Revísalo en Mis Recetas."
        self.precio_combo_field.text = ""

    # ---------- Sección 2: importar desde CSV ----------

    def _seccion_importar_csv(self):
        card = MDCard(
            orientation="vertical", size_hint_y=None, height=dp(230),
            padding=dp(16), spacing=dp(8), theme_bg_color="Custom", md_bg_color=(1, 1, 1, 1), radius=[dp(10)],
        )
        card.add_widget(MDLabel(
            text="Importar mis recetas desde CSV", bold=True, font_style="Title", role="large",
            theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1), size_hint_y=None, height=dp(30),
        ))
        card.add_widget(MDLabel(
            text="El archivo debe tener columnas: plato, precio_venta, mano_obra, "
                 "insumo, unidad, precio, merma_pct, cantidad. Una fila por cada "
                 "insumo de cada plato (el mismo nombre de plato se repite en varias filas).",
            theme_text_color="Secondary",
        ))
        btn = MDButton(MDButtonText(text="ELEGIR ARCHIVO CSV"), style="outlined", size_hint_y=None, height=dp(48))
        btn.bind(on_release=lambda x: self._abrir_selector_csv())
        card.add_widget(btn)
        return card

    def _abrir_selector_csv(self):
        if not self.file_manager:
            self.file_manager = MDFileManager(
                exit_manager=lambda *x: self.file_manager.close(),
                select_path=self._csv_elegido,
                ext=[".csv"],
            )
        self.file_manager.show(os.path.expanduser("~"))

    def _csv_elegido(self, ruta):
        self.file_manager.close()
        if not ruta.lower().endswith(".csv"):
            self.estado_label.text_color = (0.9, 0.3, 0.3, 1)
            self.estado_label.text = "⚠ Ese archivo no es un .csv"
            return

        platos_data = OrderedDict()
        try:
            with open(ruta, newline="", encoding="utf-8-sig") as f:
                for fila in csv.DictReader(f):
                    nombre_plato = fila["plato"].strip()
                    if nombre_plato not in platos_data:
                        platos_data[nombre_plato] = {
                            "precio_venta": float(fila["precio_venta"]),
                            "mano_obra": float(fila.get("mano_obra") or 0),
                            "insumos": [],
                        }
                    platos_data[nombre_plato]["insumos"].append({
                        "nombre": fila["insumo"].strip(),
                        "unidad": fila["unidad"].strip(),
                        "precio": float(fila["precio"]),
                        "merma_pct": float(fila.get("merma_pct") or 0),
                        "cantidad": float(fila["cantidad"]),
                    })
        except Exception as e:
            self.estado_label.text_color = (0.9, 0.3, 0.3, 1)
            self.estado_label.text = f"⚠ Error leyendo el CSV: {e}"
            return

        for nombre_plato, datos in platos_data.items():
            _crear_plato_con_insumos(nombre_plato, datos["precio_venta"], datos["mano_obra"], datos["insumos"])

        self.estado_label.text_color = (0.2, 0.8, 0.4, 1)
        self.estado_label.text = f"✓ Se importaron {len(platos_data)} plato(s) desde el CSV."

    # ---------- Sección 3: accesos rápidos (recetas típicas) ----------

    def _seccion_accesos_rapidos(self):
        contenedor = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        contenedor.bind(minimum_height=contenedor.setter("height"))
        contenedor.add_widget(MDLabel(
            text="Accesos rápidos", bold=True, font_style="Title", role="large",
            theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1), size_hint_y=None, height=dp(30),
        ))
        for plantilla in PLANTILLAS:
            contenedor.add_widget(self._tarjeta_plantilla(plantilla))
        return contenedor

    def _tarjeta_plantilla(self, plantilla):
        card = MDCard(
            orientation="vertical", size_hint_y=None, height=dp(130),
            padding=dp(12), spacing=dp(4), theme_bg_color="Custom", md_bg_color=(1, 1, 1, 1), radius=[dp(10)],
        )
        card.add_widget(MDLabel(text=plantilla["nombre"], bold=True,
                                 theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1)))
        card.add_widget(MDLabel(
            text=f"{len(plantilla['insumos'])} insumos  ·  venta sugerida ${plantilla['precio_venta_sugerido']:,.0f}",
            theme_text_color="Secondary",
        ))
        usar_btn = MDButton(MDButtonText(text="USAR ESTA PLANTILLA"), style="filled", size_hint_y=None, height=dp(48))
        usar_btn.bind(on_release=lambda *_: self._usar_plantilla(plantilla))
        card.add_widget(usar_btn)
        return card

    def _usar_plantilla(self, plantilla):
        insumos = [
            {"nombre": i["nombre"], "unidad": i["unidad"], "precio": i["precio_referencia"],
             "merma_pct": i["merma_pct"], "cantidad": i["cantidad"]}
            for i in plantilla["insumos"]
        ]
        _crear_plato_con_insumos(
            plantilla["nombre"], plantilla["precio_venta_sugerido"], plantilla["mano_obra_sugerida"], insumos
        )
        self.estado_label.text_color = (0.2, 0.8, 0.4, 1)
        self.estado_label.text = f"✓ '{plantilla['nombre']}' se agregó con su receta completa."