import os
import uuid

from models import confirmaciones

from kivymd.uix.dialog import MDDialog, MDDialogHeadlineText, MDDialogContentContainer, MDDialogButtonContainer
from kivy.metrics import dp
from kivy.utils import platform
from kivymd.uix.fitimage import FitImage
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.label import MDLabel, MDIcon
from kivymd.uix.card import MDCard
from kivymd.uix.relativelayout import MDRelativeLayout
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.filemanager import MDFileManager
from models import storage, fotos
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from views.utils import set_texto_boton
from views import estilo as e
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from services.analytics_service import registrar_evento

EXTENSIONES_FOTO = (".png", ".jpg", ".jpeg", ".webp")

COLUMNAS_INSUMOS = [("NOMBRE", None, "left"), ("PRECIO / FORMATO", dp(170), "right"), ("MERMA", dp(64), "right"),
                    ("COSTO CON MERMA", dp(200), "right"), ("UNIDAD", dp(190), "left")]
COLUMNAS_PLATOS = [("PLATO", None, "left"), ("INGREDIENTES", dp(100), "right"), ("PRECIO DE VENTA", dp(130), "right"),
                   ("COSTO REAL", dp(120), "right"), ("MARGEN", dp(110), "right")]
ANCHO_TABLA_COMPLETA = dp(860)


class RecetasScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="mis_recetas", md_bg_color=e.FONDO, **kwargs)
        self.modo = "insumos"
        self.formula = "actual"
        self.busqueda = ""
        self.dialog = None
        self.insumos_dialog = None
        self.menu = None
        self._insumo_editando = None
        self._plato_editando = None
        self._insumo_seleccionado = None
        self._imagen_seleccionada = None
        self.file_manager = None

        scroll = MDScrollView(do_scroll_x=False)
        self.contenido = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(16), padding=(dp(36), dp(28)))
        scroll.add_widget(self.contenido)
        self.add_widget(scroll)

        self.cabecera = MDBoxLayout(adaptive_height=True, spacing=dp(12))
        textos = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(4))
        textos.add_widget(e.etiqueta("Inicio / Mis recetas", "pequeno", e.TEXTO_TENUE))
        textos.add_widget(e.etiqueta("Mis recetas", "titulo", negrita=True))
        self.cabecera.add_widget(textos)
        acciones = MDBoxLayout(adaptive_size=True, spacing=dp(8), pos_hint={"center_y": 0.5})
        self.btn_unidades = e.boton("Confirmar unidades", lambda: setattr(self.manager, "current", "confirmar_unidades"),
                                    tipo="borde", ancho=dp(220))
        self.btn_unidades.md_bg_color, self.btn_unidades.line_color = e.AMBAR_FONDO, e.get_color_from_hex("#FDE68A")
        self.btn_unidades._txt.text_color = e.AMBAR_TEXTO
        self.btn_agregar = e.boton("+ Agregar insumo", lambda: self.abrir_dialogo(), tipo="primario", ancho=dp(170))
        acciones.add_widget(self.btn_unidades)
        acciones.add_widget(self.btn_agregar)
        self.cabecera.add_widget(acciones)
        self.contenido.add_widget(self.cabecera)

        self.barra = MDBoxLayout(adaptive_height=True, spacing=dp(10))
        self.seg_modo = e.Segmentado(None, [("insumos", "Insumos"), ("platos", "Platos")], self.cambiar_modo,
                                     activo="insumos")
        self.barra.add_widget(self.seg_modo)
        self.barra.add_widget(Widget())
        self.seg_formula = e.Segmentado("Merma", [("actual", "× (1 + m)"), ("propuesta", "÷ (1 − m)")],
                                        self._cambiar_formula, activo="actual")
        self.barra.add_widget(self.seg_formula)
        buscador = MDCard(style="outlined", theme_bg_color="Custom", md_bg_color=e.BLANCO, theme_line_color="Custom",
                          line_color=e.BORDE, radius=[dp(8)], size_hint=(None, None), size=(dp(240), dp(38)),
                          padding=(dp(10), 0), spacing=dp(6))
        buscador.add_widget(MDIcon(icon="magnify", theme_text_color="Custom", text_color=e.GRIS, size_hint_x=None,
                                   width=dp(18), pos_hint={"center_y": 0.5}, theme_font_size="Custom", font_size="17sp"))
        self.campo_buscar = TextInput(hint_text="Buscar…", multiline=False, background_normal="", background_active="",
                                      background_color=(0, 0, 0, 0), foreground_color=e.TITULO, cursor_color=e.ACENTO,
                                      font_size="14sp", padding=(0, dp(10), 0, 0), write_tab=False)
        self.campo_buscar.bind(text=self._buscar)
        buscador.add_widget(self.campo_buscar)
        self.barra.add_widget(buscador)
        self.contenido.add_widget(self.barra)

        self.tabla = e.tarjeta(padding=0)
        self.contenido.add_widget(self.tabla)
        self.bind(width=self._acomodar)

    def _acomodar(self, *args):
        ancho = self.width
        self.cabecera.orientation = "horizontal" if ancho >= dp(760) else "vertical"
        self.barra.orientation = "horizontal" if ancho >= dp(900) else "vertical"
        relleno = dp(36) if ancho >= dp(760) else dp(16)
        self.contenido.padding = (relleno, dp(28) if relleno > dp(20) else dp(20))
        compacta = ancho < ANCHO_TABLA_COMPLETA
        if compacta != getattr(self, "_compacta", None):
            self._compacta = compacta
            if self.manager is not None:
                self.refrescar()

    def on_pre_enter(self, *args):
        self.refrescar()

    def cambiar_modo(self, modo):
        self.modo = modo
        self.seg_modo.marcar(modo)
        self.refrescar()

    def _cambiar_formula(self, formula):
        self.formula = formula
        self.refrescar()

    def _buscar(self, _w, texto):
        self.busqueda = texto.strip().lower()
        self.refrescar()

    def _actualizar_botones(self, insumos, platos):
        try:
            r = confirmaciones.resumen(insumos)
            faltan = r[confirmaciones.PENDIENTE] + r[confirmaciones.REVISAR]
            set_texto_boton(self.btn_unidades, f"Confirmar unidades ({faltan})" if faltan else "Unidades confirmadas ✓")
        except confirmaciones.ErrorConfirmacion:
            set_texto_boton(self.btn_unidades, "Confirmar unidades (revisar archivo)")
        set_texto_boton(self.btn_agregar, "+ Agregar insumo" if self.modo == "insumos" else "+ Agregar plato")
        self.seg_formula.opacity = 1 if self.modo == "insumos" else 0
        self.seg_formula.disabled = self.modo != "insumos"
        set_texto_boton(self.seg_modo.botones["insumos"], f"Insumos ({len(insumos)})")
        set_texto_boton(self.seg_modo.botones["platos"], f"Platos ({len(platos)})")
        for clave, b in self.seg_modo.botones.items():
            b.width = dp(110)

    def refrescar(self):
        insumos, platos = storage.get_insumos(), storage.get_platos()
        self._actualizar_botones(insumos, platos)
        self.tabla.clear_widgets()
        compacta = self.width < ANCHO_TABLA_COMPLETA
        q = self.busqueda
        if self.modo == "insumos":
            visibles = [i for i in insumos if not q or q in i["nombre"].lower()]
            if not compacta:
                self.tabla.add_widget(e.encabezado_tabla(COLUMNAS_INSUMOS))
            try:
                datos = confirmaciones.cargar()
            except confirmaciones.ErrorConfirmacion:
                datos = {"confirmaciones": {}}
            for insumo in visibles:
                self.tabla.add_widget(self._fila_insumo(insumo, datos, compacta))
        else:
            from services import escandallo
            resumen = {p["id"]: r for p, r in escandallo.resumen_platos()}
            visibles = [p for p in platos if not q or q in p["nombre"].lower()]
            if not compacta:
                self.tabla.add_widget(e.encabezado_tabla(COLUMNAS_PLATOS))
            for plato in visibles:
                self.tabla.add_widget(self._fila_plato(plato, resumen[plato["id"]], compacta))
        if not visibles:
            texto = f"Sin resultados para «{self.busqueda}»." if q else "Aún no hay registros. Agrega el primero."
            self.tabla.add_widget(e.fila_tabla([e.celda(texto, alin="center", color=e.TEXTO_TENUE)], alto_min=dp(64)))

    def _fila_insumo(self, insumo, datos, compacta):
        from services.escandallo import factor_merma
        merma = insumo.get("merma_pct") or 0
        costo = insumo["precio"] * float(factor_merma(merma, self.formula))
        otra = "propuesta" if self.formula == "actual" else "actual"
        costo_otra = insumo["precio"] * float(factor_merma(merma, otra))
        signo = "÷ (1 − m)" if otra == "propuesta" else "× (1 + m)"
        estado = confirmaciones.estado(insumo, datos)
        if estado == confirmaciones.CONFIRMADO:
            c = confirmaciones.confirmacion(insumo, datos)
            pill = e.pildora("Confirmada · " + confirmaciones.cantidad_texto(c["contenido"], c["unidad_contenido"]), "verde")
        elif estado == confirmaciones.REVISAR:
            pill = e.pildora("Por revisar", "rojo")
        else:
            sug = confirmaciones.sugerir(insumo["unidad"])
            extra = confirmaciones.cantidad_texto(sug.contenido, sug.unidad_contenido) if sug else "sin sugerencia"
            pill = e.pildora(f"Sin confirmar · {extra}", "ambar")
        nombre = e.capitalizar(insumo["nombre"])
        precio = f"{e.pesos(insumo['precio'])} [color=#71717A]/ {insumo['unidad']}[/color]"
        merma_txt = e.porcentaje(merma * 100, 0) if merma else "—"
        costo_txt = f"[b]{e.pesos(costo)}[/b] [color=#A1A1AA]({signo}: {e.pesos(costo_otra)})[/color]"
        abrir = lambda i=insumo: self.abrir_dialogo(i)
        if compacta:
            caja = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(4))
            caja.add_widget(e.celda(nombre, negrita=True))
            caja.add_widget(e.celda(f"{precio} · merma {merma_txt}", estilo="pequeno", color=e.TEXTO, markup=True))
            caja.add_widget(e.celda(f"Con merma: {costo_txt}", estilo="pequeno", color=e.TEXTO, markup=True))
            caja.add_widget(pill)
            return e.fila_tabla([caja], abrir, relleno=dp(14))
        return e.fila_tabla([
            e.celda(nombre, negrita=True),
            e.celda(precio, COLUMNAS_INSUMOS[1][1], "right", markup=True),
            e.celda(merma_txt, COLUMNAS_INSUMOS[2][1], "right", color=e.AMBAR if merma >= 0.1 else e.TITULO),
            e.celda(costo_txt, COLUMNAS_INSUMOS[3][1], "right", markup=True),
            e.celda(MDBoxLayout(pill, size_hint_y=None, height=dp(26)), COLUMNAS_INSUMOS[4][1]),
        ], abrir)

    def _fila_plato(self, plato, res, compacta):
        nombre = MDBoxLayout(spacing=dp(10), size_hint_y=None, height=dp(40))
        ruta = storage.ruta_imagen(plato.get("imagen"))
        if ruta:
            nombre.add_widget(FitImage(source=ruta, size_hint=(None, None), size=(dp(40), dp(40)), radius=[dp(6)],
                                       pos_hint={"center_y": 0.5}))
        nombre.add_widget(e.celda(e.capitalizar(plato["nombre"]), negrita=True))
        pill = e.pildora(e.porcentaje(res.margen), e.tono_margen(res.margen))
        n = len(res.filas)
        abrir = lambda p=plato: self.abrir_dialogo(p)
        if compacta:
            caja = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(4))
            caja.add_widget(nombre)
            caja.add_widget(e.celda(f"Venta {e.pesos(res.precio)} · costo {e.pesos(res.costo)} · {n} ingredientes",
                                    estilo="pequeno", color=e.TEXTO))
            caja.add_widget(pill)
            return e.fila_tabla([caja], abrir, relleno=dp(14))
        margen = MDBoxLayout(size_hint_y=None, height=dp(26))
        margen.add_widget(Widget())
        margen.add_widget(pill)
        return e.fila_tabla([
            nombre,
            e.celda(str(n), COLUMNAS_PLATOS[1][1], "right"),
            e.celda(e.pesos(res.precio), COLUMNAS_PLATOS[2][1], "right"),
            e.celda(e.pesos(res.costo), COLUMNAS_PLATOS[3][1], "right"),
            e.celda(margen, COLUMNAS_PLATOS[4][1]),
        ], abrir, alto_min=dp(56))

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
            text=str(round(insumo["merma_pct"] * 100, 2)) if insumo else "0",
            input_filter="float",
        )
        self.estado_form = self._etiqueta_estado()
        content = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, height=dp(254))
        for f in (self.nombre_field, self.unidad_field, self.precio_field, self.merma_field, self.estado_form):
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
                on_release=lambda x: self._confirmar(
                    f"¿Eliminar el insumo '{insumo['nombre']}'? También se quitará de las recetas que lo usan.",
                    lambda: self._eliminar_insumo(insumo["id"]),
                )
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

    def _etiqueta_estado(self):
        """Línea para avisar en el propio formulario por qué no se pudo guardar."""
        return MDLabel(text="", size_hint_y=None, height=dp(24), font_style="Body", role="small",
                       theme_text_color="Custom", text_color=(0.85, 0.25, 0.25, 1))

    def _avisar(self, texto):
        self.estado_form.text = texto

    def _confirmar(self, texto, accion):
        """Pide confirmación antes de una acción que borra datos."""
        def aceptar(*_):
            confirmacion.dismiss()
            accion()

        confirmacion = MDDialog(
            MDDialogHeadlineText(text="Confirmar"),
            MDDialogContentContainer(MDLabel(text=texto, adaptive_height=True)),
            MDDialogButtonContainer(
                MDButton(MDButtonText(text="CANCELAR"), style="text", on_release=lambda *_: confirmacion.dismiss()),
                MDButton(MDButtonText(text="ELIMINAR"), style="text", on_release=aceptar),
            ),
        )
        confirmacion.open()

    def _guardar_insumo(self):
        nombre = self.nombre_field.text.strip()
        unidad = self.unidad_field.text.strip()
        if not nombre or not unidad:
            self._avisar("Completa el nombre y la unidad.")
            return
        try:
            precio = float(self.precio_field.text or 0)
            merma_pct = float(self.merma_field.text or 0) / 100
        except ValueError:
            self._avisar("El precio y la merma deben ser números.")
            return
        if precio < 0 or not 0 <= merma_pct < 1:
            self._avisar("El precio no puede ser negativo y la merma va de 0 a 99%.")
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

        vista_foto = self._crear_vista_foto(storage.ruta_imagen(self._imagen_seleccionada))
        self.elegir_foto_txt = MDButtonText(text="Cambiar foto" if self._imagen_seleccionada else "Elegir foto",
                                            size_hint_y=None, height=dp(48))
        elegir_foto_btn = MDButton(
            self.elegir_foto_txt, style="text", size_hint_y=None, height=dp(48),
            on_release=lambda x: self._abrir_selector_imagen()
        )

        self.estado_form = self._etiqueta_estado()
        content = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, height=dp(414))
        content.add_widget(vista_foto)
        content.add_widget(elegir_foto_btn)
        for f in (self.nombre_field, self.precio_field, self.mano_obra_field, self.estado_form):
            content.add_widget(f)

        botones = [
            MDButton(MDButtonText(text="CANCELAR", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48), on_release=lambda x: self.dialog.dismiss()),
            MDButton(MDButtonText(text="GUARDAR", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48), on_release=lambda x: self._guardar_plato()),
        ]
        if plato:
            # ELIMINAR e INSUMOS van en una fila propia: los cuatro botones juntos no caben en
            # el ancho de un teléfono y GUARDAR quedaba fuera de la pantalla
            acciones = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
            acciones.add_widget(MDButton(
                MDButtonText(text="INSUMOS", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48),
                on_release=lambda x: self._abrir_gestion_insumos(plato)
            ))
            acciones.add_widget(MDButton(
                MDButtonText(text="ELIMINAR", size_hint_y=None, height=dp(48)), style="text", size_hint_y=None, height=dp(48),
                on_release=lambda x: self._confirmar(
                    f"¿Eliminar el plato '{plato['nombre']}' y su receta?",
                    lambda: self._eliminar_plato(plato["id"]),
                ),
            ))
            content.add_widget(acciones)
            content.height += dp(58)

        self.dialog = MDDialog(
            MDDialogHeadlineText(text="Editar plato" if plato else "Nuevo plato"),
            MDDialogContentContainer(content),
            MDDialogButtonContainer(*botones)
        )
        self.dialog.open()

    def _guardar_plato(self):
        nombre = self.nombre_field.text.strip()
        if not nombre:
            self._avisar("Escribe el nombre del plato.")
            return
        try:
            precio_venta = float(self.precio_field.text or 0)
            mano_obra = float(self.mano_obra_field.text or 0)
        except ValueError:
            self._avisar("El precio y la mano de obra deben ser números.")
            return
        if precio_venta < 0 or mano_obra < 0:
            self._avisar("Los montos no pueden ser negativos.")
            return
        if self._plato_editando:
            storage.update_plato(
                self._plato_editando["id"], nombre, precio_venta, mano_obra, self._imagen_seleccionada
            )
        else:
            storage.add_plato(nombre, precio_venta, mano_obra, self._imagen_seleccionada)
            registrar_evento("plato_creado", {
                "nombre_plato": nombre,
                "precio_venta": precio_venta,
                "costo_mano_obra": mano_obra,
                "tiene_imagen": bool(self._imagen_seleccionada),
            })
        self.dialog.dismiss()
        self.refrescar()

    def _crear_vista_foto(self, ruta):
        """Recuadro de la foto: muestra la elegida o, si no hay, un aviso de que se puede tocar."""
        tarjeta = MDCard(size_hint_y=None, height=dp(150), radius=[dp(8)], theme_bg_color="Custom",
                         md_bg_color=(0.92, 0.92, 0.95, 1), on_release=lambda *_: self._abrir_selector_imagen())
        capa = MDRelativeLayout()
        self.preview_imagen = FitImage(source=ruta or "", radius=[dp(8)], opacity=1 if ruta else 0)
        self.preview_vacio = MDRelativeLayout(opacity=0 if ruta else 1)
        self.preview_vacio.add_widget(MDIcon(icon="image-plus", theme_font_size="Custom", font_size="40sp",
                                             pos_hint={"center_x": 0.5, "center_y": 0.62},
                                             theme_text_color="Custom", text_color=(0.4, 0.45, 0.55, 1)))
        self.preview_vacio.add_widget(MDLabel(text="Toca para elegir una foto", halign="center",
                                              size_hint_y=None, height=dp(24), pos_hint={"center_y": 0.3},
                                              theme_text_color="Custom", text_color=(0.4, 0.45, 0.55, 1)))
        capa.add_widget(self.preview_imagen)
        capa.add_widget(self.preview_vacio)
        tarjeta.add_widget(capa)
        return tarjeta

    def _mostrar_foto(self, ruta):
        self.preview_imagen.source = ruta
        self.preview_imagen.opacity = 1
        self.preview_vacio.opacity = 0
        self.elegir_foto_txt.text = "Cambiar foto"

    def _abrir_selector_imagen(self):
        os.makedirs(storage.imagenes_dir(), exist_ok=True)  # carpeta única de fotos, dentro de los datos persistentes
        if platform == "android":
            # Galería del sistema con miniaturas; no necesita permisos de almacenamiento
            from views.selector_fotos_android import elegir_foto
            self._avisar("")
            elegir_foto(self._foto_de_galeria)
            return
        if not self.file_manager:
            self.file_manager = MDFileManager(
                exit_manager=lambda *x: self.file_manager.close(),
                select_path=self._imagen_elegida,
                preview=True,
                ext=list(EXTENSIONES_FOTO),
            )
        self.file_manager.show(storage.imagenes_dir())

    def _foto_de_galeria(self, nombre, contenido, error):
        if error:
            self._avisar(f"No se pudo leer la foto: {error}")
        elif contenido is not None:
            self._guardar_foto(nombre, contenido)

    def _imagen_elegida(self, ruta):
        self.file_manager.close()
        if not ruta.lower().endswith(EXTENSIONES_FOTO):
            self._avisar("Elige una imagen PNG o JPG.")
            return
        imagenes_dir = storage.imagenes_dir()
        if os.path.dirname(os.path.abspath(ruta)) == os.path.abspath(imagenes_dir):
            # Ya es una foto de la app: se usa tal cual, sin duplicarla
            self._imagen_seleccionada = os.path.basename(ruta)
            self._mostrar_foto(ruta)
            return
        try:
            with open(ruta, "rb") as f:
                contenido = f.read()
        except OSError as e:
            self._avisar(f"No se pudo leer la foto: {e.strerror or e}")
            return
        self._guardar_foto(os.path.basename(ruta), contenido)

    def _guardar_foto(self, nombre, contenido):
        try:
            destino = fotos.guardar(nombre, contenido, storage.imagenes_dir())
        except OSError as e:
            self._avisar(f"No se pudo guardar la foto: {e.strerror or e}")
            return
        # En el JSON se guarda solo el nombre del archivo; storage.ruta_imagen() arma la ruta
        self._imagen_seleccionada = os.path.basename(destino)
        self._mostrar_foto(destino)

    def _eliminar_plato(self, plato_id):
        storage.delete_plato(plato_id)
        self.dialog.dismiss()
        self.refrescar()

    def _abrir_gestion_insumos(self, plato):
        self.dialog.dismiss()
        self._plato_editando = plato
        self._insumo_seleccionado = None  # no arrastrar una selección hecha en otro plato

        self.lista_insumos_box = MDBoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
        self.lista_insumos_box.bind(minimum_height=self.lista_insumos_box.setter("height"))

        scroll_insumos = MDScrollView(size_hint_y=1)
        scroll_insumos.add_widget(self.lista_insumos_box)

        self.cantidad_field = MDTextField(MDTextFieldHintText(text="Cantidad a usar"), input_filter="float")
        
        self.selector_insumo_btn = MDButton(
            MDButtonText(text="Elegir insumo"),
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
        insumos = storage.get_insumos()
        if not insumos:
            self.estado_label.text_color = (0.9, 0.3, 0.3, 1)
            self.estado_label.text = "Primero crea insumos en la pestaña INSUMOS."
            return
        items = [
            {"text": insumo["nombre"], "on_release": lambda i=insumo: self._seleccionar_insumo(i)}
            for insumo in insumos
        ]
        self.menu = MDDropdownMenu(caller=boton, items=items, width_mult=4)
        self.menu.open()

    def _seleccionar_insumo(self, insumo):
        self._insumo_seleccionado = insumo
        set_texto_boton(self.selector_insumo_btn, insumo["nombre"])
        self.menu.dismiss()
        # La cantidad se multiplica por el precio del insumo, así que va en su misma unidad
        self.estado_label.text_color = (0.4, 0.45, 0.55, 1)
        self.estado_label.text = f"Cantidad en {insumo['unidad']}"

    def _agregar_insumo_a_receta(self):
        if not self._insumo_seleccionado:
            self.estado_label.text_color = (0.9, 0.3, 0.3, 1)
            self.estado_label.text = "Toca 'Elegir insumo' y selecciona uno."
            return
        try:
            cantidad = float(self.cantidad_field.text or 0)
        except ValueError:
            self.estado_label.text_color = (0.9, 0.3, 0.3, 1)
            self.estado_label.text = "La cantidad debe ser un número."
            return
        if cantidad <= 0:
            self.estado_label.text_color = (0.9, 0.3, 0.3, 1)
            self.estado_label.text = "Ingresa una cantidad mayor a 0."
            return

        storage.add_insumo_a_plato(self._plato_editando["id"], self._insumo_seleccionado["id"], cantidad)
        self.estado_label.text = f"{self._insumo_seleccionado['nombre']} agregado."
        self.estado_label.text_color = (0.2, 0.8, 0.4, 1)
        self.cantidad_field.text = ""
        set_texto_boton(self.selector_insumo_btn, "Elegir insumo")
        self._insumo_seleccionado = None
        self._refrescar_lista_insumos_receta()

    def _quitar_insumo(self, rel_id):
        storage.quitar_insumo_de_plato(rel_id)
        self._refrescar_lista_insumos_receta()