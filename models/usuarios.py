"""Persistencia de usuarios (<datos>/usuarios.json). Solo guarda datos; no valida nada."""
import json
import os
from datetime import datetime

from models import rutas


def _cargar():
    archivo = rutas.archivo_usuarios()
    if not os.path.exists(archivo):
        return {}
    with open(archivo, "r", encoding="utf-8") as f:
        return json.load(f)


def _guardar(usuarios):
    archivo = rutas.archivo_usuarios()
    os.makedirs(os.path.dirname(archivo), exist_ok=True)
    # privado=True: solo el dueño puede leer/escribir el archivo (permisos 600)
    rutas.escribir_json_atomico(archivo, usuarios, privado=True)


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
