import os
import shutil
import uuid

from kivymd.uix.dialog import MDDialog, MDDialogHeadlineText, MDDialogContentContainer, MDDialogButtonContainer
from kivy.metrics import dp
from kivymd.uix.fitimage import FitImage
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.filemanager import MDFileManager
from models import storage
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.fitimage import FitImage

IMAGENES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "images"
)

class RecetasScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="mis_recetas", md_bg_color=(0.95, 0.95, 0.95, 1), **kwargs)
        self.modo = "insumos"
        self.dialog = None
        self.insumos_dialog = None
        self.menu = None
        self._insumo_editando = None
        self._plato_editando = None
        self._insumo_seleccionado = None
        self._imagen_seleccionada = None
        self.file_manager = None

        root = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(14))

        back = MDButton(MDButtonText(text="‹  Volver al inicio", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48))
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "inicio"))
        root.add_widget(back)

        root.add_widget(
            MDLabel(text="Mis Recetas", font_style="Headline", role="medium", bold=True, size_hint_y=None, height=dp(52),
                    theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1))
        )

        tabs = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.btn_insumos = MDButton(
            MDButtonText(text="INSUMOS", size_hint_y=None, height=dp(48)),
            style="text", size_hint_y=None, height=dp(48),
            on_release=lambda x: self.cambiar_modo("insumos")
        )
        self.btn_platos = MDButton(
            MDButtonText(text="PLATOS", size_hint_y=None, height=dp(48)),
            style="text", size_hint_y=None, height=dp(48),
            on_release=lambda x: self.cambiar_modo("platos")
        )
        tabs.add_widget(self.btn_insumos)
        tabs.add_widget(self.btn_platos)
        root.add_widget(tabs)

        scroll = MDScrollView()
        self.container = MDBoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
        self.container.bind(minimum_height=self.container.setter("height"))
        scroll.add_widget(self.container)
        root.add_widget(scroll)

        agregar_btn = MDButton(MDButtonText(text="+ Agregar", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48))
        agregar_btn.bind(on_release=lambda x: self.abrir_dialogo())
        root.add_widget(agregar_btn)

        self.add_widget(root)
        self._marcar_tab_activo()

    def on_pre_enter(self, *args):
        self.refrescar()

    def _marcar_tab_activo(self):
        activo = (0.2, 0.6, 1, 1)
        inactivo = (0.6, 0.6, 0.6, 1)
        self.btn_insumos.theme_text_color = "Custom"
        self.btn_platos.theme_text_color = "Custom"
        self.btn_insumos.text_color = activo if self.modo == "insumos" else inactivo
        self.btn_platos.text_color = activo if self.modo == "platos" else inactivo

    def cambiar_modo(self, modo):
        self.modo = modo
        self._marcar_tab_activo()
        self.refrescar()

    def refrescar(self):
        self.container.clear_widgets()
        if self.modo == "insumos":
            for insumo in storage.get_insumos():
                texto = (
                    f"{insumo['nombre']} — ${insumo['precio']:.0f} / {insumo['unidad']} "
                    f"(merma {insumo['merma_pct'] * 100:.0f}%)"
                )
                self.container.add_widget(self._fila(texto, lambda i=insumo: self.abrir_dialogo(i)))
        else:
            from services.calculo_costos import costo_real_plato, margen
            for plato in storage.get_platos():
                usados = storage.get_insumos_de_plato(plato["id"])
                costo = costo_real_plato(usados, plato["mano_obra"])
                m = margen(plato["precio_venta"], costo)
                texto = (
                    f"{plato['nombre']} — venta ${plato['precio_venta']:.0f} "
                    f"/ costo ${costo:.0f} / margen {m:.1f}%"
                )
                self.container.add_widget(
                    self._fila(texto, lambda p=plato: self.abrir_dialogo(p), imagen=plato.get("imagen"))
                )

    def _fila(self, texto, on_tap, imagen=None):
        fila = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(8))

        if imagen :
            nombre_archivo = os.path.basename(imagen)
            ruta_imagen = os.path.join(IMAGENES_DIR, nombre_archivo)
            if os.path.exists(ruta_imagen):
                fila.add_widget(FitImage(source=ruta_imagen, size_hint_x=None, width=dp(44), radius=[dp(8)]))
                
        lbl = MDLabel(text=texto, theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1))
        fila.add_widget(lbl)
        btn = MDIconButton(icon="pencil", theme_icon_color="Custom", icon_color=(0.6, 0.6, 0.6, 1))
        btn.bind(on_release=lambda x: on_tap())
        fila.add_widget(btn)
        return fila

    def abrir_dialogo(self, item=None):
        if self.modo == "insumos":
            self._abrir_dialogo_insumo(item)
        else:
            self._abrir_dialogo_plato(item)

    def _abrir_dialogo_insumo(self, insumo=None):
        self._insumo_editando = insumo
        self.nombre_field = MDTextField(
            MDTextFieldHintText(text="Nombre"),
            text=insumo["nombre"] if insumo else ""
        )
        self.unidad_field = MDTextField(
            MDTextFieldHintText(text="Unidad (kg / lt / un)"),
            text=insumo["unidad"] if insumo else ""
        )
        self.precio_field = MDTextField(
            MDTextFieldHintText(text="Precio de compra"),
            text=str(insumo["precio"]) if insumo else "",
            input_filter="float"
        )
        self.merma_field = MDTextField(
            MDTextFieldHintText(text="Merma (%)"),
            text=str(insumo["merma_pct"] * 100) if insumo else "0",
        )
        content = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, height=dp(220))
        for f in (self.nombre_field, self.unidad_field, self.precio_field, self.merma_field):
            content.add_widget(f)

        botones = [
            MDButton(
                MDButtonText(text="CANCELAR", size_hint_y=None, height=dp(48)), 
                style="text", 
                on_release=lambda x: self.dialog.dismiss()
            ),
            MDButton(
                MDButtonText(text="GUARDAR", size_hint_y=None, height=dp(48)), 
                style="text", 
                on_release=lambda x: self._guardar_insumo()
            )
        ]
        if insumo:
            botones.insert(0, MDButton(
                MDButtonText(text="ELIMINAR", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48),
                on_release=lambda x: self._eliminar_insumo(insumo["id"])
            ))

        self.dialog = MDDialog(
            MDDialogHeadlineText(
                text="Editar insumo" if insumo else "Nuevo insumo",
            ),
            MDDialogContentContainer(
                content,
            ),
            MDDialogButtonContainer(
                *botones
            ),
        )
        self.dialog.open()

    def _guardar_insumo(self):
        nombre = self.nombre_field.text.strip()
        unidad = self.unidad_field.text.strip()
        try:
            precio = float(self.precio_field.text or 0)
            merma_pct = float(self.merma_field.text or 0) / 100
        except ValueError:
            return
        if not nombre or not unidad:
            return
        if self._insumo_editando:
            storage.update_insumo(self._insumo_editando["id"], nombre, unidad, precio, merma_pct)
        else:
            storage.add_insumo(nombre, unidad, precio, merma_pct)
        self.dialog.dismiss()
        self.refrescar()

    def _eliminar_insumo(self, insumo_id):
        storage.delete_insumo(insumo_id)
        self.dialog.dismiss()
        self.refrescar()

    def _abrir_dialogo_plato(self, plato=None):
        self._plato_editando = plato
        self._imagen_seleccionada = plato["imagen"] if plato else None

        self.nombre_field = MDTextField(MDTextFieldHintText(text="Nombre del plato"), text=plato["nombre"] if plato else "")
        self.precio_field = MDTextField(
            MDTextFieldHintText(text="Precio de venta"), text=str(plato["precio_venta"]) if plato else "", input_filter="float"
        )
        self.mano_obra_field = MDTextField(
            MDTextFieldHintText(text="Costo mano de obra"), text=str(plato["mano_obra"]) if plato else "0", input_filter="float"
        )

        self.preview_imagen = FitImage(
            source=self._imagen_seleccionada if self._imagen_seleccionada else "",
            size_hint_y=None, height=dp(90), radius=[dp(8)],
        )
        elegir_foto_btn = MDButton(
            MDButtonText(text="Elegir foto", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48),
            on_release=lambda x: self._abrir_selector_imagen()
        )

        content = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, height=dp(320))
        content.add_widget(self.preview_imagen)
        content.add_widget(elegir_foto_btn)
        for f in (self.nombre_field, self.precio_field, self.mano_obra_field):
            content.add_widget(f)

        botones = [
            MDButton(MDButtonText(text="CANCELAR", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48), on_release=lambda x: self.dialog.dismiss()),
            MDButton(MDButtonText(text="GUARDAR", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48), on_release=lambda x: self._guardar_plato()),
        ]
        if plato:
            botones.insert(0, MDButton(
                MDButtonText(text="INSUMOS", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48),
                on_release=lambda x: self._abrir_gestion_insumos(plato)
            ))
            botones.insert(0, MDButton(
                MDButtonText(text="ELIMINAR", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48),
                on_release=lambda x: self._eliminar_plato(plato["id"]),
            ))

        self.dialog = MDDialog(
            MDDialogHeadlineText(text="Editar plato" if plato else "Nuevo plato"),
            MDDialogContentContainer(content),
            MDDialogButtonContainer(*botones)
        )
        self.dialog.open()

    def _guardar_plato(self):
        nombre = self.nombre_field.text.strip()
        try:
            precio_venta = float(self.precio_field.text or 0)
            mano_obra = float(self.mano_obra_field.text or 0)
        except ValueError:
            return
        if not nombre:
            return
        if self._plato_editando:
            storage.update_plato(
                self._plato_editando["id"], nombre, precio_venta, mano_obra, self._imagen_seleccionada
            )
        else:
            storage.add_plato(nombre, precio_venta, mano_obra, self._imagen_seleccionada)
        self.dialog.dismiss()
        self.refrescar()

    def _abrir_selector_imagen(self):
        if not self.file_manager:
            self.file_manager = MDFileManager(
                exit_manager=lambda *x: self.file_manager.close(),
                select_path=self._imagen_elegida,
                preview=True,
            )
        self.file_manager.show(os.path.abspath("SmartCost/data/imagenes"))

    def _imagen_elegida(self, ruta):
        self.file_manager.close()
        if not ruta.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            return

        os.makedirs(IMAGENES_DIR, exist_ok=True)
        nuevo_nombre = os.path.basename(ruta)
        destino = os.path.join(IMAGENES_DIR, nuevo_nombre)

        if ruta != destino:
            shutil.copy(ruta, destino)

        self._imagen_seleccionada = f"SmartCost/data/imagenes/{nuevo_nombre}"
        self.preview_imagen.source = destino

    def _eliminar_plato(self, plato_id):
        storage.delete_plato(plato_id)
        self.dialog.dismiss()
        self.refrescar()

    def _abrir_gestion_insumos(self, plato):
        self.dialog.dismiss()
        self._plato_editando = plato

        self.lista_insumos_box = MDBoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
        self.lista_insumos_box.bind(minimum_height=self.lista_insumos_box.setter("height"))

        scroll_insumos = MDScrollView(size_hint_y=1)
        scroll_insumos.add_widget(self.lista_insumos_box)

        self.cantidad_field = MDTextField(MDTextFieldHintText(text="Cantidad a usar"), input_filter="float")
        
        self.selector_insumo_btn = MDButton(
            MDButtonText(text="Elegir insumo", size_hint_y=None, height=dp(48)),
            on_release=self._abrir_selector_insumo,
            pos_hint={"center_x": 0.5}
        )
        
        self.estado_label = MDLabel(
            text="", size_hint_y=None, height=dp(24),
            theme_text_color="Custom", text_color=(0.9, 0.3, 0.3, 1),
            halign="center"
        )

        content = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, height=dp(420))
        content.add_widget(MDLabel(text="Insumos actuales:", bold=True, size_hint_y=None, height=dp(24)))
        content.add_widget(scroll_insumos)
        content.add_widget(self.selector_insumo_btn)
        content.add_widget(self.cantidad_field)
        content.add_widget(self.estado_label)
        
        btn_agregar_receta = MDButton(
            MDButtonText(text="AGREGAR A LA RECETA", size_hint_y=None, height=dp(48)),
            on_release=lambda x: self._agregar_insumo_a_receta(),
            style="text",
            size_hint_y=None,
            height=dp(48)
        )
        content.add_widget(btn_agregar_receta)

        boton_cerrar = MDButton(
            MDButtonText(text="CERRAR", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48),
            on_release=lambda x: self._cerrar_gestion_insumos()
        )

        self.insumos_dialog = MDDialog(
            MDDialogHeadlineText(text=f"Insumos de: {plato['nombre']}"),
            MDDialogContentContainer(content),
            MDDialogButtonContainer(boton_cerrar)
        )
        self._refrescar_lista_insumos_receta()
        self.insumos_dialog.open()

    def _cerrar_gestion_insumos(self):
        self.insumos_dialog.dismiss()
        self.refrescar()

    def _refrescar_lista_insumos_receta(self):
        self.lista_insumos_box.clear_widgets()
        for rel in storage.get_insumos_de_plato(self._plato_editando["id"]):
            fila = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36))
            fila.add_widget(MDLabel(text=f"{rel['nombre']} — {rel['cantidad']} {rel['unidad']}"))
            btn = MDIconButton(icon="delete", on_release=lambda x, rel_id=rel["rel_id"]: self._quitar_insumo(rel_id))
            fila.add_widget(btn)
            self.lista_insumos_box.add_widget(fila)

    def _abrir_selector_insumo(self, boton):
        items = [
            {"text": insumo["nombre"], "on_release": lambda i=insumo: self._seleccionar_insumo(i)}
            for insumo in storage.get_insumos()
        ]
        self.menu = MDDropdownMenu(caller=boton, items=items, width_mult=4)
        self.menu.open()

    def _seleccionar_insumo(self, insumo):
        self._insumo_seleccionado = insumo
        self.selector_insumo_btn.text = insumo["nombre"]
        self.menu.dismiss()

    def _agregar_insumo_a_receta(self):
        if not self._insumo_seleccionado:
            self.estado_label.text_color = (0.9, 0.3, 0.3, 1)
            self.estado_label.text = "⚠ Toca 'Elegir insumo' y selecciona uno."
            return
        try:
            cantidad = float(self.cantidad_field.text or 0)
        except ValueError:
            self.estado_label.text_color = (0.9, 0.3, 0.3, 1)
            self.estado_label.text = "⚠ La cantidad debe ser un número."
            return
        if cantidad <= 0:
            self.estado_label.text_color = (0.9, 0.3, 0.3, 1)
            self.estado_label.text = "⚠ Ingresa una cantidad mayor a 0."
            return

        storage.add_insumo_a_plato(self._plato_editando["id"], self._insumo_seleccionado["id"], cantidad)
        self.estado_label.text = f"✓ {self._insumo_seleccionado['nombre']} agregado."
        self.estado_label.text_color = (0.2, 0.8, 0.4, 1)
        self.cantidad_field.text = ""
        self.selector_insumo_btn.text = "Elegir insumo"
        self._insumo_seleccionado = None
        self._refrescar_lista_insumos_receta()

    def _quitar_insumo(self, rel_id):
        storage.quitar_insumo_de_plato(rel_id)
        self._refrescar_lista_insumos_receta()