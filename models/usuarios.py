"""Persistencia de usuarios (data/usuarios.json). Solo guarda datos; no valida nada."""
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USUARIOS_FILE = os.path.join(BASE_DIR, "data", "usuarios.json")


def _cargar():
    if not os.path.exists(USUARIOS_FILE):
        return {}
    with open(USUARIOS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _guardar(usuarios):
    os.makedirs(os.path.dirname(USUARIOS_FILE), exist_ok=True)
    with open(USUARIOS_FILE, "w", encoding="utf-8") as f:
        json.dump(usuarios, f, indent=4, ensure_ascii=False)
    try:
        os.chmod(USUARIOS_FILE, 0o600)  # solo el dueño puede leer/escribir el archivo
    except OSError:
        pass


def get_usuario(nombre):
    """Devuelve el dict del usuario o None. El nombre no distingue mayúsculas."""
    return _cargar().get(nombre.lower())


def add_usuario(nombre, salt, hash_password, iteraciones):
    usuarios = _cargar()
    usuarios[nombre.lower()] = {
        "nombre": nombre,
        "salt": salt,
        "hash": hash_password,
        "iteraciones": iteraciones,
        "intentos_fallidos": 0,
        "bloqueado_hasta": 0,
        "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _guardar(usuarios)


def actualizar_usuario(nombre, **campos):
    """Actualiza campos sueltos (intentos_fallidos, bloqueado_hasta, hash, salt, iteraciones)."""
    usuarios = _cargar()
    clave = nombre.lower()
    if clave in usuarios:
        usuarios[clave].update(campos)
        _guardar(usuarios)
