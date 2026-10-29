"""Pantalla de login / registro."""
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText, MDTextFieldTrailingIcon
from services import auth
from views import marca
from views.utils import set_texto_boton

ROJO = (0.8, 0.2, 0.2, 1)
ALTO_LOGIN = dp(498)  # alto de la tarjeta para iniciar sesión
ALTO_BASE_REGISTRO = dp(544)  # alto de la tarjeta en modo registro sin contar la lista de requisitos
VERDE = (0.1, 0.5, 0.2, 1)
ALTO_LOGO = dp(76)
ALTO_PIE = dp(24)


class AcentoMarca(Widget):
    """Trazo bajo el nombre: turquesa de la marca con un toque rojo de la bandera chilena."""

    def __init__(self, **kwargs):
        # Ancho fijo centrado con pos_hint: no depende de que el layout le asigne ancho
        super().__init__(size_hint=(None, None), size=(dp(44), dp(4)), pos_hint={"center_x": 0.5}, **kwargs)
        with self.canvas:
            Color(*marca.TURQUESA)
            self._turquesa = RoundedRectangle(radius=[dp(2)])
            Color(*marca.ROJO_CHILE)
            self._rojo = RoundedRectangle(radius=[dp(2)])
        self.bind(pos=self._dibujar, size=self._dibujar)

    def _dibujar(self, *args):
        self._turquesa.pos, self._turquesa.size = (self.x, self.y), (dp(32), self.height)
        self._rojo.pos, self._rojo.size = (self.x + dp(36), self.y), (dp(8), self.height)


class LoginScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="login", md_bg_color=marca.AZUL_OSCURO, **kwargs)
        self.modo_registro = False

        # Fondo: cordillera de los Andes al anochecer (recursos/marca/fondo_login.jpg, ~30 KB)
        self.add_widget(Image(source=marca.FONDO_LOGIN, fit_mode="cover"))

        # Todo va en un ScrollView: si la tarjeta de registro no cabe (teléfono chico o
        # teclado abierto) se desplaza en vez de quedar cortada
        self.scroll = MDScrollView(do_scroll_x=False)
        root = MDBoxLayout(orientation="vertical", padding=dp(24), spacing=dp(14), size_hint_y=None)
        self.root_box = root
        root.add_widget(Widget())  # espaciador: centra el contenido
        self.logo = Image(source=marca.LOGO, size_hint=(None, None), size=(ALTO_LOGO, ALTO_LOGO),
                          pos_hint={"center_x": 0.5})
        root.add_widget(self.logo)

        card = MDCard(
            orientation="vertical", size_hint_y=None, height=ALTO_LOGIN,
            padding=dp(24), spacing=dp(12), radius=[dp(20)],
            style="elevated", theme_bg_color="Custom", md_bg_color=(1, 1, 1, 0.97),
        )
        card.add_widget(MDLabel(
            text=marca.nombre_marca(), markup=True, font_style="Headline", role="medium", bold=True, halign="center",
            size_hint_y=None, height=dp(48),
        ))
        card.add_widget(AcentoMarca())
        self.subtitulo = MDLabel(
            text="Inicia sesión para continuar", halign="center",
            theme_text_color="Custom", text_color=marca.TEXTO_SUAVE, size_hint_y=None, height=dp(28),
        )
        card.add_widget(self.subtitulo)

        self.usuario_field = MDTextField(MDTextFieldHintText(text="Usuario"), mode="outlined")
        self.ojo_password = MDTextFieldTrailingIcon(icon="eye-off")
        self.ojo_confirmar = MDTextFieldTrailingIcon(icon="eye-off")
        self.password_field = MDTextField(
            MDTextFieldHintText(text="Contraseña"), self.ojo_password, mode="outlined", password=True,
        )
        self.confirmar_field = MDTextField(
            MDTextFieldHintText(text="Repetir contraseña"), self.ojo_confirmar, mode="outlined", password=True,
        )
        # Tocar cualquiera de los dos ojitos muestra/oculta ambas contraseñas
        # El MDTextField se queda con los toques y dibuja el ícono por su cuenta (el widget del
        # ícono no tiene posición real), así que se escucha en el campo y se revisa si el
        # toque cayó en la zona derecha, donde está dibujado el ojito.
        self.password_field.bind(on_touch_down=self._tocar_campo)
        self.confirmar_field.bind(on_touch_down=self._tocar_campo)
        self.password_field.bind(text=lambda *_: self._actualizar_requisitos())
        self.usuario_field.bind(text=lambda *_: self._actualizar_requisitos())
        card.add_widget(self.usuario_field)
        card.add_widget(self.password_field)
        self.card = card

        # Lista de requisitos de la contraseña (solo visible al registrarse)
        self.requisitos = MDLabel(
            text="", markup=True, font_size="13sp", theme_text_color="Custom", text_color=(0.4, 0.45, 0.55, 1),
            size_hint_y=None, height=dp(84),
        )
        # En pantallas angostas los requisitos ocupan más líneas: la lista y la tarjeta crecen
        self.requisitos.bind(texture_size=self._ajustar_requisitos)

        self.mensaje = MDLabel(
            text="", halign="center", theme_text_color="Custom", text_color=ROJO,
            size_hint_y=None, height=dp(48),
        )
        card.add_widget(self.mensaje)

        self.txt_accion = MDButtonText(text="INGRESAR", theme_text_color="Custom", text_color=marca.BLANCO, bold=True)
        self.btn_accion = MDButton(self.txt_accion, style="filled", size_hint_y=None, height=dp(48), pos_hint={"center_x": 0.5},
                                   theme_bg_color="Custom", md_bg_color=marca.TURQUESA_OSCURO)
        self.btn_accion.bind(on_release=lambda *_: self._enviar())
        card.add_widget(self.btn_accion)

        self.txt_cambiar = MDButtonText(text="¿No tienes cuenta? Regístrate", theme_text_color="Custom",
                                        text_color=marca.TURQUESA_OSCURO)
        self.btn_cambiar = MDButton(self.txt_cambiar, style="text", size_hint_y=None, height=dp(40), pos_hint={"center_x": 0.5})
        self.btn_cambiar.bind(on_release=lambda *_: self._cambiar_modo())
        card.add_widget(self.btn_cambiar)

        # Enter en el campo de contraseña también envía el formulario
        self.password_field.bind(on_text_validate=lambda *_: self._enviar())
        self.confirmar_field.bind(on_text_validate=lambda *_: self._enviar())

        root.add_widget(card)

        # Origen, discreto y sobre la parte más oscura de la cordillera
        pie = MDBoxLayout(size_hint=(None, None), height=ALTO_PIE, spacing=dp(8), pos_hint={"center_x": 0.5})
        pie.add_widget(Image(source=marca.BANDERA_CHILE, size_hint=(None, None), size=(dp(21), dp(14)),
                             pos_hint={"center_y": 0.5}))
        origen = MDLabel(text="Desarrollado en Chile", font_style="Label", role="large", adaptive_width=True,
                         theme_text_color="Custom", text_color=(1, 1, 1, 0.85), pos_hint={"center_y": 0.5})
        pie.add_widget(origen)
        origen.bind(width=lambda *_: setattr(pie, "width", dp(21) + dp(8) + origen.width))
        root.add_widget(pie)
        root.add_widget(Widget())  # espaciador

        self.scroll.add_widget(root)
        self.add_widget(self.scroll)
        # El contenido ocupa al menos toda la pantalla (para quedar centrado) y crece si no cabe
        for w, prop in ((self.scroll, "height"), (card, "height")):
            w.bind(**{prop: self._ajustar_alto})

    def _mostrar_logo(self, visible):
        self.logo.height = ALTO_LOGO if visible else 0
        self.logo.opacity = 1 if visible else 0
        self._ajustar_alto()

    def _ajustar_alto(self, *args):
        fijo = dp(24) * 2 + self.logo.height + self.card.height + ALTO_PIE + dp(14) * 4
        self.root_box.height = max(self.scroll.height, fijo)

    def on_pre_enter(self, *args):
        self._limpiar()
        self._ocultar_passwords()

    def _ocultar_passwords(self):
        for campo, ojo in ((self.password_field, self.ojo_password), (self.confirmar_field, self.ojo_confirmar)):
            campo.password = True
            ojo.icon = "eye-off"

    def _tocar_campo(self, campo, touch):
        """Si el toque cae sobre el ojito (extremo derecho del campo), muestra/oculta las contraseñas."""
        if not campo.get_root_window() or not campo.collide_point(*touch.pos):
            return False
        if touch.x < campo.right - dp(56):
            return False  # toque normal en el campo: se deja escribir
        mostrar = self.password_field.password  # si estaba oculta, ahora se muestra
        for c, ojo in ((self.password_field, self.ojo_password), (self.confirmar_field, self.ojo_confirmar)):
            c.password = not mostrar
            ojo.icon = "eye-off" if not mostrar else "eye"
        return True

    def _ajustar_requisitos(self, etiqueta, tamano):
        etiqueta.height = max(dp(84), tamano[1])
        if self.modo_registro:
            self.card.height = ALTO_BASE_REGISTRO + etiqueta.height

    def _actualizar_requisitos(self):
        if not self.modo_registro:
            return
        items = []
        for texto, cumple in auth.requisitos_password(self.password_field.text, self.usuario_field.text):
            color = "1a8f3c" if cumple else "888888"
            marca = "+" if cumple else "-"
            items.append(f"[color={color}]{marca} {texto}[/color]")
        # de a dos por línea para que ocupe poco espacio
        self.requisitos.text = "\n".join("     ".join(items[i:i + 2]) for i in range(0, len(items), 2))

    def _limpiar(self):
        for f in (self.usuario_field, self.password_field, self.confirmar_field):
            f.text = ""
        self._mensaje("", ROJO)

    def _mensaje(self, texto, color):
        self.mensaje.text = texto
        self.mensaje.text_color = color

    def _cambiar_modo(self):
        self.modo_registro = not self.modo_registro
        if self.modo_registro:
            self.card.add_widget(self.confirmar_field, index=self.card.children.index(self.mensaje) + 1)
            self.card.add_widget(self.requisitos, index=self.card.children.index(self.confirmar_field) + 1)
            self.card.height = ALTO_BASE_REGISTRO + self.requisitos.height
            self._mostrar_logo(False)  # la tarjeta de registro es alta: así cabe sin desplazarse
            self._actualizar_requisitos()
            self.subtitulo.text = "Crea tu cuenta"
            self.txt_accion.text = "CREAR CUENTA"
            self.txt_cambiar.text = "¿Ya tienes cuenta? Inicia sesión"
        else:
            self.card.remove_widget(self.confirmar_field)
            self.card.remove_widget(self.requisitos)
            self.card.height = ALTO_LOGIN
            self._mostrar_logo(True)
            self.subtitulo.text = "Inicia sesión para continuar"
            self.txt_accion.text = "INGRESAR"
            self.txt_cambiar.text = "¿No tienes cuenta? Regístrate"
        self.confirmar_field.text = ""
        self._ocultar_passwords()
        self._mensaje("", ROJO)

    def _enviar(self):
        usuario, clave = self.usuario_field.text, self.password_field.text
        if self.modo_registro:
            ok, msg = auth.registrar(usuario, clave, self.confirmar_field.text)
            if ok:
                self._cambiar_modo()          # vuelve al login con el mensaje de éxito
                self.usuario_field.text = usuario.strip()
                self._mensaje(msg, VERDE)
            else:
                self._mensaje(msg, ROJO)
        else:
            ok, msg = auth.iniciar_sesion(usuario, clave)
            if ok:
                self.manager.current = "inicio"
            else:
                self.password_field.text = ""   # nunca se deja la clave fallida en pantalla
                self._mensaje(msg, ROJO)
