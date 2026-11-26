"""Pantalla de inicio de sesión y registro (diseño aprobado en el prototipo del 2026-11-26).

Fondo claro con puntos, la marca arriba a la izquierda, pestañas "Iniciar sesión" /
"Crear cuenta" en la misma pantalla y campos con etiqueta e ícono. Solo cambia la
presentación: las reglas (services/auth.py), los intentos y el bloqueo siguen iguales.
"""
from kivy.graphics import Color, Rectangle
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.card import MDCard
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDIcon, MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField, MDTextFieldLeadingIcon, MDTextFieldTrailingIcon
from kivy.utils import get_color_from_hex

from services import auth
from services.analytics_service import registrar_evento
from views import marca
from views.utils import alto_segun_texto

FONDO = get_color_from_hex("#FAFBFC")
PUNTO = (211, 219, 227)                  # #d3dbe3
FONDO_PESTANAS = get_color_from_hex("#EEF2F5")
BLANCO = (1, 1, 1, 1)
TEXTO = marca.TEXTO
TEXTO_ETIQUETA = get_color_from_hex("#2A3646")
TEXTO_SUAVE = marca.TEXTO_SUAVE
ACENTO = marca.TURQUESA_OSCURO           # texto blanco encima: 4,9:1
DESHABILITADO = get_color_from_hex("#E3E8EE")
VERDE = get_color_from_hex("#1B6B43")
ROJO = get_color_from_hex("#9B1C14")
FONDO_ERROR = get_color_from_hex("#FDECEA")
FONDO_EXITO = get_color_from_hex("#E3F3EA")
BORDE_CAMPO = get_color_from_hex("#D5DDE6")
PASO_PUNTOS = 20                         # separación de los puntos del fondo (dp)


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


def _etiqueta(texto="", estilo=("Body", "medium"), color=TEXTO, negrita=False, **kw):
    return alto_segun_texto(MDLabel(text=texto, font_style=estilo[0], role=estilo[1], bold=negrita,
                                    theme_text_color="Custom", text_color=color, **kw))


def _campo(icono, password=False):
    """Campo con ícono a la izquierda (y ojito a la derecha si es contraseña)."""
    partes = [MDTextFieldLeadingIcon(icon=icono)]
    ojo = None
    if password:
        ojo = MDTextFieldTrailingIcon(icon="eye-off")
        partes.append(ojo)
    campo = MDTextField(*partes, mode="outlined", password=password, theme_bg_color="Custom",
                        fill_color_normal=BLANCO, fill_color_focus=BLANCO, theme_line_color="Custom",
                        line_color_normal=BORDE_CAMPO, line_color_focus=ACENTO)
    return campo, ojo


def _con_etiqueta(texto, campo, ayuda=None):
    caja = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(7))
    caja.add_widget(_etiqueta(texto, ("Body", "medium"), TEXTO_ETIQUETA, negrita=True))
    caja.add_widget(campo)
    if ayuda is not None:
        caja.add_widget(ayuda)
    return caja


class LoginScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(name="login", md_bg_color=FONDO, **kwargs)
        self.modo_registro = False
        self.add_widget(FondoPuntos())

        # En un ScrollView: si no cabe (teléfono chico o teclado abierto) se desplaza
        self.scroll = MDScrollView(do_scroll_x=False)
        raiz = MDBoxLayout(orientation="vertical", padding=(dp(24), dp(24), dp(24), dp(20)),
                           spacing=dp(22), size_hint_y=None)
        self.raiz = raiz

        # Marca
        fila_marca = MDBoxLayout(adaptive_height=True, spacing=dp(12))
        sello = MDBoxLayout(size_hint=(None, None), size=(dp(44), dp(44)), padding=dp(6),
                            md_bg_color=marca.AZUL_OSCURO, radius=[dp(12)])
        sello.add_widget(Image(source=marca.LOGO))
        fila_marca.add_widget(sello)
        textos_marca = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(1),
                                   pos_hint={"center_y": 0.5})
        textos_marca.add_widget(_etiqueta(marca.nombre_marca(), ("Title", "large"), negrita=True, markup=True))
        textos_marca.add_widget(_etiqueta("Costos y márgenes para tu cocina", ("Body", "small"), TEXTO_SUAVE))
        fila_marca.add_widget(textos_marca)
        raiz.add_widget(fila_marca)

        # Título
        bloque_titulo = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(8),
                                    padding=(0, dp(14), 0, 0))
        self.titulo = _etiqueta("", ("Headline", "small"), negrita=True)
        self.bajada = _etiqueta("", ("Body", "large"), TEXTO_SUAVE)
        bloque_titulo.add_widget(self.titulo)
        bloque_titulo.add_widget(self.bajada)
        raiz.add_widget(bloque_titulo)

        # Pestañas
        pestanas = MDBoxLayout(size_hint_y=None, height=dp(52), padding=dp(4), spacing=dp(4),
                               md_bg_color=FONDO_PESTANAS, radius=[dp(14)])
        self.pestana_entrar = self._pestana("Iniciar sesión", False)
        self.pestana_crear = self._pestana("Crear cuenta", True)
        pestanas.add_widget(self.pestana_entrar)
        pestanas.add_widget(self.pestana_crear)
        raiz.add_widget(pestanas)

        # Formulario
        form = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(16))
        self.usuario_field, _ = _campo("account-outline")
        self.ayuda_usuario = _etiqueta("3 a 20 caracteres: letras, números, punto o guion bajo.",
                                       ("Body", "small"), TEXTO_SUAVE)
        self.slot_ayuda_usuario = MDBoxLayout(orientation="vertical", adaptive_height=True)
        form.add_widget(_con_etiqueta("Usuario", self.usuario_field, self.slot_ayuda_usuario))

        self.password_field, self.ojo_password = _campo("lock-outline", password=True)
        form.add_widget(_con_etiqueta("Contraseña", self.password_field))

        # Solo al crear cuenta: requisitos y repetir contraseña
        self.slot_crear = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(16))
        self.requisitos = MDGridLayout(cols=2, adaptive_height=True, spacing=(dp(10), dp(6)))
        self.confirmar_field, self.ojo_confirmar = _campo("lock-outline", password=True)
        self.ayuda_repetir = _etiqueta("", ("Body", "small"), TEXTO_SUAVE)
        self.bloque_crear = [self.requisitos, _con_etiqueta("Repetir contraseña", self.confirmar_field,
                                                            self.ayuda_repetir)]
        form.add_widget(self.slot_crear)

        # Mensaje de error o de éxito
        self.slot_mensaje = MDBoxLayout(orientation="vertical", adaptive_height=True)
        self.caja_mensaje = MDBoxLayout(adaptive_height=True, spacing=dp(8), padding=(dp(12), dp(10)),
                                        radius=[dp(10)])
        self.icono_mensaje = MDIcon(icon="alert-circle-outline", theme_text_color="Custom",
                                    size_hint_x=None, width=dp(22), pos_hint={"center_y": 0.5})
        self.mensaje = _etiqueta("", ("Body", "medium"))
        self.caja_mensaje.add_widget(self.icono_mensaje)
        self.caja_mensaje.add_widget(self.mensaje)
        form.add_widget(self.slot_mensaje)

        # Tarjeta tocable en vez de MDButton: así el texto va centrado con la flecha a la derecha
        # (MDButton de KivyMD 2.0 alinea su contenido a la izquierda)
        self.txt_accion = MDLabel(text="", adaptive_size=True, font_style="Title", role="medium", bold=True,
                                  theme_text_color="Custom", text_color=BLANCO, pos_hint={"center_y": 0.5})
        self.ico_accion = MDIcon(icon="arrow-right", theme_text_color="Custom", text_color=BLANCO,
                                 size_hint_x=None, width=dp(24), pos_hint={"center_y": 0.5})
        self.btn_accion = MDCard(style="filled", theme_bg_color="Custom", md_bg_color=ACENTO,
                                 size_hint_y=None, height=dp(54), radius=[dp(14)], padding=(dp(16), 0),
                                 spacing=dp(8))
        for w in (Widget(), self.txt_accion, self.ico_accion, Widget()):
            self.btn_accion.add_widget(w)
        self.btn_accion.bind(on_release=lambda *_: self._enviar())
        form.add_widget(self.btn_accion)
        raiz.add_widget(form)

        raiz.add_widget(Widget())  # empuja el pie hacia abajo cuando sobra espacio

        # Pie
        linea = MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=FONDO_PESTANAS)
        raiz.add_widget(linea)
        pie = MDBoxLayout(size_hint_y=None, height=dp(24), spacing=dp(6))
        pie.add_widget(MDIcon(icon="shield-check-outline", theme_text_color="Custom", text_color=VERDE,
                              size_hint_x=None, width=dp(20), pos_hint={"center_y": 0.5}))
        pie.add_widget(MDLabel(text="Tus datos se guardan en este teléfono", font_style="Body", role="small",
                               theme_text_color="Custom", text_color=TEXTO_SUAVE, pos_hint={"center_y": 0.5}))
        pie.add_widget(Image(source=marca.BANDERA_CHILE, size_hint=(None, None), size=(dp(18), dp(12)),
                             pos_hint={"center_y": 0.5}))
        chile = MDLabel(text="Hecho en Chile", font_style="Body", role="small", adaptive_width=True,
                        theme_text_color="Custom", text_color=TEXTO_SUAVE, pos_hint={"center_y": 0.5})
        pie.add_widget(chile)
        raiz.add_widget(pie)

        self.scroll.add_widget(raiz)
        self.add_widget(self.scroll)
        # Ocupa al menos toda la pantalla (pie abajo) y crece si el contenido no cabe
        raiz.bind(minimum_height=self._ajustar_alto)
        self.scroll.bind(height=self._ajustar_alto)

        # Ojito: el MDTextField se queda con los toques y dibuja el ícono por su cuenta, así que
        # se escucha en el campo y se revisa si el toque cayó en la zona derecha
        self.password_field.bind(on_touch_down=self._tocar_campo)
        self.confirmar_field.bind(on_touch_down=self._tocar_campo)
        for campo in (self.usuario_field, self.password_field, self.confirmar_field):
            campo.bind(text=lambda *_: self._actualizar())
        # Enter en la contraseña también envía el formulario
        self.password_field.bind(on_text_validate=lambda *_: self._enviar())
        self.confirmar_field.bind(on_text_validate=lambda *_: self._enviar())

        self._aplicar_modo()

    # ---------- armado ----------

    def _pestana(self, texto, crear):
        txt = MDButtonText(text=texto, theme_text_color="Custom", bold=True,
                           pos_hint={"center_x": 0.5, "center_y": 0.5})
        b = MDButton(txt, style="filled", theme_bg_color="Custom", theme_width="Custom", theme_height="Custom",
                     size_hint=(1, None), height=dp(44), radius=[dp(10)])
        b._txt = txt
        b.bind(on_release=lambda *_: self._ir_a(crear))
        return b

    def _ajustar_alto(self, *args):
        self.raiz.height = max(self.scroll.height, self.raiz.minimum_height)

    # ---------- estado ----------

    def on_pre_enter(self, *args):
        self._limpiar()
        self._ocultar_passwords()

    def _ir_a(self, crear):
        if crear != self.modo_registro:
            self._cambiar_modo()

    def _cambiar_modo(self):
        self.modo_registro = not self.modo_registro
        self.confirmar_field.text = ""
        self.password_field.text = ""
        self._ocultar_passwords()
        self._mensaje("", ROJO)
        self._aplicar_modo()

    def _aplicar_modo(self):
        crear = self.modo_registro
        self.titulo.text = "Crea tu cuenta" if crear else "Accede a tus costos"
        self.bajada.text = ("Empieza a calcular el costo real de tus platos." if crear
                            else "Calcula, organiza y haz crecer tu negocio.")
        self.txt_accion.text = "Crear cuenta" if crear else "Iniciar sesión"
        for pestana, activa in ((self.pestana_entrar, not crear), (self.pestana_crear, crear)):
            pestana.md_bg_color = BLANCO if activa else FONDO_PESTANAS
            pestana._txt.text_color = TEXTO if activa else TEXTO_SUAVE
        self.slot_ayuda_usuario.clear_widgets()
        self.slot_crear.clear_widgets()
        if crear:
            self.slot_ayuda_usuario.add_widget(self.ayuda_usuario)
            for w in self.bloque_crear:
                self.slot_crear.add_widget(w)
        self._actualizar()

    def _actualizar(self):
        """Requisitos de la contraseña, coincidencia y botón (solo cambia algo al crear cuenta)."""
        if not self.modo_registro:
            self._boton_habilitado(True)
            return
        usuario, clave, repetir = self.usuario_field.text, self.password_field.text, self.confirmar_field.text
        self.requisitos.clear_widgets()
        todos = True
        for texto, cumple in auth.requisitos_password(clave, usuario):
            ok = bool(clave) and cumple
            todos = todos and ok
            fila = MDBoxLayout(adaptive_height=True, spacing=dp(6))
            fila.add_widget(MDIcon(icon="check-circle-outline" if ok else "circle-outline",
                                   theme_text_color="Custom", text_color=VERDE if ok else TEXTO_SUAVE,
                                   font_size="16sp", size_hint=(None, None), size=(dp(18), dp(18)),
                                   pos_hint={"center_y": 0.5}))
            fila.add_widget(_etiqueta(texto, ("Body", "small"), VERDE if ok else TEXTO_SUAVE))
            self.requisitos.add_widget(fila)
        usuario_ok = auth.validar_usuario(usuario.strip())[0]
        self.ayuda_usuario.text_color = ROJO if usuario and not usuario_ok else TEXTO_SUAVE
        coincide = bool(repetir) and repetir == clave
        self.ayuda_repetir.text = ("" if not repetir else
                                   "Las contraseñas coinciden." if coincide else "Las contraseñas no coinciden.")
        self.ayuda_repetir.text_color = VERDE if coincide else ROJO
        self._boton_habilitado(usuario_ok and todos and coincide)

    def _boton_habilitado(self, habilitado):
        self.btn_accion.disabled = not habilitado
        self.btn_accion.md_bg_color = ACENTO if habilitado else DESHABILITADO
        color = BLANCO if habilitado else TEXTO_SUAVE
        self.txt_accion.text_color = color
        self.ico_accion.text_color = color

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

    def _limpiar(self):
        for f in (self.usuario_field, self.password_field, self.confirmar_field):
            f.text = ""
        self._mensaje("", ROJO)

    def _mensaje(self, texto, color):
        self.slot_mensaje.clear_widgets()
        if not texto:
            return
        exito = color == VERDE
        self.caja_mensaje.md_bg_color = FONDO_EXITO if exito else FONDO_ERROR
        self.icono_mensaje.icon = "check-circle-outline" if exito else "alert-circle-outline"
        self.icono_mensaje.text_color = color
        self.mensaje.text = texto
        self.mensaje.text_color = color
        self.slot_mensaje.add_widget(self.caja_mensaje)

    # ---------- acciones ----------

    def _enviar(self):
        if self.btn_accion.disabled:
            return  # crear cuenta con datos incompletos (también al pulsar Enter)
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
                registrar_evento("login_exitoso")  # sin nombre de usuario: dato personal
                self.manager.current = "inicio"
            else:
                registrar_evento("login_fallido", {"motivo": msg})
                self.password_field.text = ""   # nunca se deja la clave fallida en pantalla
                self._mensaje(msg, ROJO)
