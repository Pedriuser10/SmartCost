"""Ubicación de los datos persistentes (cuentas, recetas y fotos) y su migración inicial.

Los datos viven en <user_data_dir>/datos, fuera de la carpeta del código: en Android
cada actualización borra y vuelve a extraer la carpeta de la app, pero no user_data_dir.
La carpeta data/ del proyecto (o del APK) es solo el origen de la primera copia y el
lugar de las fotos de ejemplo.

Reglas de la migración:
- Nunca sobrescribe un archivo que ya existe en el destino.
- Valida el origen y la copia antes de darla por buena; el origen nunca se modifica.
- Si algo falla, no hay ubicación alternativa: los datos quedan bloqueados (ninguna
  lectura ni escritura) y la app muestra el error, así no se crea una base vacía.
"""
import json
import logging
import os
import shutil

log = logging.getLogger("smartcost.datos")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEN_DIR = os.path.join(BASE_DIR, "data")
ORIGEN_IMAGENES_DIR = os.path.join(ORIGEN_DIR, "imagenes")

ARCHIVOS_JSON = ("app.json", "usuarios.json")
PRIVADOS = {"usuarios.json"}  # se crean con permisos 600
EXTENSIONES_IMAGEN = (".png", ".jpg", ".jpeg", ".webp")

_datos_dir = None
error = None  # mensaje del último fallo de migrar(); mientras exista, los datos quedan bloqueados


class DatosNoDisponibles(RuntimeError):
    """Se intentó leer o escribir datos sin una carpeta de datos lista."""


def configurar(user_data_dir):
    global _datos_dir, error
    _datos_dir = os.path.join(user_data_dir, "datos")
    error = None


def datos_dir():
    if _datos_dir is None:
        raise DatosNoDisponibles("La carpeta de datos no está configurada.")
    if error:
        raise DatosNoDisponibles(error)
    return _datos_dir


def archivo_app():
    return os.path.join(datos_dir(), "app.json")


def archivo_usuarios():
    return os.path.join(datos_dir(), "usuarios.json")


def imagenes_dir():
    return os.path.join(datos_dir(), "imagenes")


# ---------- ESCRITURA ATÓMICA ----------

def escribir_atomico(ruta, contenido, privado=False):
    """Escribe bytes en ruta.tmp y lo renombra encima de ruta con os.replace.

    Si algo falla a mitad de camino, el archivo original queda intacto y se borra el .tmp.
    """
    tmp = ruta + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600 if privado else 0o644)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(contenido)
            f.flush()
            os.fsync(f.fileno())
        if privado:
            os.chmod(tmp, 0o600)  # por si el .tmp ya existía con otros permisos
        os.replace(tmp, ruta)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def escribir_json_atomico(ruta, datos, privado=False):
    contenido = json.dumps(datos, indent=4, ensure_ascii=False).encode("utf-8")
    escribir_atomico(ruta, contenido, privado)


# ---------- MIGRACIÓN ----------

def _validar_json(contenido, ruta):
    try:
        json.loads(contenido.decode("utf-8"))
    except ValueError as e:  # JSONDecodeError y UnicodeDecodeError
        raise ValueError(f"{os.path.basename(ruta)} no es un JSON válido ({e})") from None


def _copiar_json(origen, destino, privado):
    with open(origen, "rb") as f:
        contenido = f.read()
    _validar_json(contenido, origen)
    escribir_atomico(destino, contenido, privado)
    with open(destino, "rb") as f:
        if f.read() != contenido:
            raise OSError(f"la copia de {os.path.basename(origen)} no coincide con el original")


def _migrar_imagenes(destino_dir):
    """Copia las fotos de ejemplo que falten. Un fallo aquí no bloquea la app:
    storage.ruta_imagen() sigue encontrando la foto en la carpeta de origen."""
    if not os.path.isdir(ORIGEN_IMAGENES_DIR):
        return
    for nombre in sorted(os.listdir(ORIGEN_IMAGENES_DIR)):
        origen = os.path.join(ORIGEN_IMAGENES_DIR, nombre)
        destino = os.path.join(destino_dir, nombre)
        if (not os.path.isfile(origen) or not nombre.lower().endswith(EXTENSIONES_IMAGEN)
                or nombre.startswith("grafico_") or os.path.exists(destino)):
            continue
        tmp = destino + ".tmp"
        try:
            shutil.copyfile(origen, tmp)
            os.replace(tmp, destino)
        except OSError as e:
            log.warning("No se pudo copiar la foto %s: %s", nombre, e)
            try:
                os.remove(tmp)
            except OSError:
                pass


def migrar():
    """Prepara la carpeta de datos. Devuelve True si quedó lista; si no, deja el motivo en `error`."""
    global error
    if _datos_dir is None:
        raise DatosNoDisponibles("Llama a configurar() antes de migrar().")
    error = None
    try:
        os.makedirs(os.path.join(_datos_dir, "imagenes"), exist_ok=True)
        for nombre in ARCHIVOS_JSON:
            destino = os.path.join(_datos_dir, nombre)
            origen = os.path.join(ORIGEN_DIR, nombre)
            if os.path.exists(destino):
                # Ya hay datos del usuario: se validan, pero nunca se reemplazan
                with open(destino, "rb") as f:
                    _validar_json(f.read(), destino)
            elif os.path.exists(origen):
                _copiar_json(origen, destino, nombre in PRIVADOS)
                log.info("Datos iniciales copiados: %s -> %s", nombre, _datos_dir)
    except (OSError, ValueError) as e:
        error = f"No se pudieron preparar los datos en {_datos_dir}: {e}"
        log.error(error)
        return False
    _migrar_imagenes(os.path.join(_datos_dir, "imagenes"))
    return True
