"""Lógica de autenticación pura (sin KivyMD): validación, hash, bloqueo y verificación.

Medidas de seguridad:
- Contraseñas con hash PBKDF2-HMAC-SHA256 (600.000 iteraciones) y sal aleatoria única por usuario.
- Política de contraseña fuerte (largo, mayúscula, minúscula, número, símbolo, no común).
- Comparación en tiempo constante (hmac.compare_digest).
- Mensaje genérico: no revela si falló el usuario o la contraseña.
- Bloqueo temporal tras varios intentos fallidos (frena la fuerza bruta).
- El hash se actualiza solo si algún día se suben las iteraciones.
"""
import hashlib
import hmac
import os
import re
import time

from models import usuarios

MIN_USUARIO = 3
MAX_USUARIO = 20
MIN_PASSWORD = 8
MAX_PASSWORD = 64
ITERACIONES = 600_000      # recomendación OWASP para PBKDF2-HMAC-SHA256
MAX_INTENTOS = 5           # intentos fallidos antes de bloquear
BLOQUEO_SEGUNDOS = 300     # 5 minutos

_RE_USUARIO = re.compile(r"^[A-Za-z0-9_.]+$")
_COMUNES = {
    "12345678", "123456789", "1234567890", "password", "password1", "password123",
    "contraseña", "contrasena", "qwerty123", "qwertyui", "abc12345", "iloveyou",
    "admin123", "admin1234", "bienvenido", "chile2024", "chile2025", "chile2026",
    "smartcost", "smartcost1", "smartcost123",
}

# Usuario con sesión iniciada (None si nadie ha entrado)
usuario_actual = None


def _hash(password, salt_bytes, iteraciones):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iteraciones).hex()


def requisitos_password(password, nombre=""):
    """Lista de (descripción, cumple) para mostrar el avance mientras se escribe."""
    nombre = nombre.strip().lower()
    return [
        (f"{MIN_PASSWORD}+ caracteres", len(password) >= MIN_PASSWORD),
        ("una mayúscula", any(c.isupper() for c in password)),
        ("una minúscula", any(c.islower() for c in password)),
        ("un número", any(c.isdigit() for c in password)),
        ("un símbolo (!@#$...)", any(not c.isalnum() for c in password)),
        ("no contiene tu usuario", not nombre or nombre not in password.lower()),
        ("no es una clave común", password.lower() not in _COMUNES),
    ]


def validar_usuario(nombre):
    if len(nombre) < MIN_USUARIO or len(nombre) > MAX_USUARIO:
        return False, f"El usuario debe tener entre {MIN_USUARIO} y {MAX_USUARIO} caracteres."
    if not _RE_USUARIO.match(nombre):
        return False, "El usuario solo puede tener letras, números, punto y guion bajo."
    return True, ""


def validar_password(password, nombre=""):
    if len(password) > MAX_PASSWORD:
        return False, f"La contraseña no puede superar {MAX_PASSWORD} caracteres."
    faltantes = [txt for txt, ok in requisitos_password(password, nombre) if not ok]
    if faltantes:
        return False, "La contraseña no cumple: " + ", ".join(faltantes) + "."
    return True, ""


def registrar(nombre, password, confirmacion):
    """Crea un usuario. Devuelve (ok, mensaje)."""
    nombre = nombre.strip()
    ok, msg = validar_usuario(nombre)
    if not ok:
        return False, msg
    ok, msg = validar_password(password, nombre)
    if not ok:
        return False, msg
    if password != confirmacion:
        return False, "Las contraseñas no coinciden."
    if usuarios.get_usuario(nombre):
        return False, "Ese usuario ya existe."
    salt = os.urandom(16)
    usuarios.add_usuario(nombre, salt.hex(), _hash(password, salt, ITERACIONES), ITERACIONES)
    return True, "Cuenta creada. Ya puedes iniciar sesión."


def iniciar_sesion(nombre, password):
    """Verifica credenciales. Devuelve (ok, mensaje)."""
    global usuario_actual
    nombre = nombre.strip()
    if not nombre or not password:
        return False, "Ingresa usuario y contraseña."

    datos = usuarios.get_usuario(nombre)
    if not datos:
        # Hace el mismo trabajo que un login real para que el tiempo de respuesta
        # no delate si el usuario existe o no.
        _hash(password, b"\x00" * 16, ITERACIONES)
        return False, "Usuario o contraseña incorrectos."

    ahora = time.time()
    if datos.get("bloqueado_hasta", 0) > ahora:
        minutos = int((datos["bloqueado_hasta"] - ahora) // 60) + 1
        return False, f"Cuenta bloqueada por demasiados intentos. Intenta en {minutos} min."

    iteraciones = datos.get("iteraciones", 200_000)  # cuentas creadas con la versión anterior
    calculado = _hash(password, bytes.fromhex(datos["salt"]), iteraciones)
    if not hmac.compare_digest(datos["hash"], calculado):
        intentos = datos.get("intentos_fallidos", 0) + 1
        if intentos >= MAX_INTENTOS:
            usuarios.actualizar_usuario(nombre, intentos_fallidos=0, bloqueado_hasta=ahora + BLOQUEO_SEGUNDOS)
            return False, f"Demasiados intentos. Cuenta bloqueada {BLOQUEO_SEGUNDOS // 60} minutos."
        usuarios.actualizar_usuario(nombre, intentos_fallidos=intentos)
        restantes = MAX_INTENTOS - intentos
        return False, f"Usuario o contraseña incorrectos. Te quedan {restantes} intento(s)."

    # Login correcto: se reinician los contadores y se sube el hash si quedó con menos iteraciones
    cambios = {"intentos_fallidos": 0, "bloqueado_hasta": 0}
    if iteraciones < ITERACIONES:
        salt = os.urandom(16)
        cambios.update(salt=salt.hex(), hash=_hash(password, salt, ITERACIONES), iteraciones=ITERACIONES)
    usuarios.actualizar_usuario(nombre, **cambios)
    usuario_actual = datos["nombre"]
    return True, f"Bienvenido, {usuario_actual}."


def cerrar_sesion():
    global usuario_actual
    usuario_actual = None
