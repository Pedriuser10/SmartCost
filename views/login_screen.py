"""Pantalla de login / registro."""
from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText, MDTextFieldTrailingIcon
from services import auth
from views.utils import set_texto_boton

ROJO = (0.8, 0.2, 0.2, 1)
VERDE = (0.1, 0.5, 0.2, 1)


class LoginScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="login", md_bg_color=(0.97, 0.97, 0.99, 1), **kwargs)
        self.modo_registro = False

        root = MDBoxLayout(orientation="vertical", padding=dp(24))
        root.add_widget(MDBoxLayout())  # espaciador: centra la tarjeta

        card = MDCard(
            orientation="vertical", size_hint_y=None, height=dp(480),
            padding=dp(24), spacing=dp(12), radius=[dp(16)],
            style="elevated", theme_bg_color="Custom", md_bg_color=(1, 1, 1, 1),
        )
        card.add_widget(MDLabel(
            text="SmartCost", font_style="Headline", role="medium", bold=True, halign="center",
            theme_text_color="Custom", text_color=(0.1, 0.1, 0.1, 1), size_hint_y=None, height=dp(48),
        ))
        self.subtitulo = MDLabel(
            text="Inicia sesión para continuar", halign="center",
            theme_text_color="Custom", text_color=(0.4, 0.45, 0.55, 1), size_hint_y=None, height=dp(28),
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

        self.mensaje = MDLabel(
            text="", halign="center", theme_text_color="Custom", text_color=ROJO,
            size_hint_y=None, height=dp(48),
        )
        card.add_widget(self.mensaje)

        self.txt_accion = MDButtonText(text="INGRESAR")
        self.btn_accion = MDButton(self.txt_accion, style="filled", size_hint_y=None, height=dp(48), pos_hint={"center_x": 0.5})
        self.btn_accion.bind(on_release=lambda *_: self._enviar())
        card.add_widget(self.btn_accion)

        self.txt_cambiar = MDButtonText(text="¿No tienes cuenta? Regístrate")
        self.btn_cambiar = MDButton(self.txt_cambiar, style="text", size_hint_y=None, height=dp(40), pos_hint={"center_x": 0.5})
        self.btn_cambiar.bind(on_release=lambda *_: self._cambiar_modo())
        card.add_widget(self.btn_cambiar)

        # Enter en el campo de contraseña también envía el formulario
        self.password_field.bind(on_text_validate=lambda *_: self._enviar())
        self.confirmar_field.bind(on_text_validate=lambda *_: self._enviar())

        root.add_widget(card)
        root.add_widget(MDBoxLayout())
        self.add_widget(root)

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
            self.card.height = dp(610)
            self._actualizar_requisitos()
            self.subtitulo.text = "Crea tu cuenta"
            self.txt_accion.text = "CREAR CUENTA"
            self.txt_cambiar.text = "¿Ya tienes cuenta? Inicia sesión"
        else:
            self.card.remove_widget(self.confirmar_field)
            self.card.remove_widget(self.requisitos)
            self.card.height = dp(480)
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
