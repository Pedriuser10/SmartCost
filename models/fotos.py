"""Guardado de las fotos de los platos en la carpeta de datos persistentes.

Las fotos de cámara pesan varios MB, vienen giradas mediante EXIF (que Kivy ignora) y
suelen llamarse igual en carpetas distintas (IMG_0001.jpg). Por eso se enderezan, se
reducen y se guardan sin pisar nunca otra foto ya guardada.
"""
import io
import logging
import os

log = logging.getLogger("smartcost.fotos")

LADO_MAXIMO = 1600  # px; de sobra para las tarjetas y la vista previa
CALIDAD_JPEG = 85


def preparar(nombre, contenido):
    """Devuelve (nombre, contenido) listos para guardar: enderezados y reducidos.

    Si la foto ya está derecha y es chica se devuelve tal cual (sin recomprimir). Si
    Pillow no puede abrirla, también se guarda tal cual: es mejor una foto pesada que
    perderla.
    """
    try:
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(contenido)) as original:
            formato = original.format
            girada = _tiene_orientacion(original)
            imagen = ImageOps.exif_transpose(original)
            grande = max(imagen.size) > LADO_MAXIMO
            if not (girada or grande):
                return nombre, contenido
            if grande:
                imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
            salida = io.BytesIO()
            base = os.path.splitext(nombre)[0]
            if formato == "PNG":
                imagen.save(salida, "PNG", optimize=True)
                return base + ".png", salida.getvalue()
            if imagen.mode not in ("RGB", "L"):
                imagen = imagen.convert("RGB")
            imagen.save(salida, "JPEG", quality=CALIDAD_JPEG, optimize=True)
            return base + ".jpg", salida.getvalue()
    except Exception as e:  # formato no soportado, archivo dañado...
        log.warning("No se pudo procesar la foto %s (%s); se guarda sin cambios", nombre, e)
        return nombre, contenido


def _tiene_orientacion(imagen):
    try:
        return imagen.getexif().get(0x0112, 1) not in (1, None)  # 0x0112 = Orientation
    except Exception:
        return False


def guardar(nombre, contenido, carpeta):
    """Guarda la foto en `carpeta` y devuelve su ruta final.

    Si ya hay una foto idéntica se reutiliza; si el nombre está ocupado por otra foto
    se guarda como nombre_1.jpg, nombre_2.jpg, ... La escritura es atómica (.tmp + os.replace).
    """
    nombre, contenido = preparar(os.path.basename(nombre), contenido)
    base, ext = os.path.splitext(nombre)
    destino, n = os.path.join(carpeta, base + ext), 1
    while os.path.exists(destino):
        with open(destino, "rb") as f:
            if f.read() == contenido:
                return destino
        destino, n = os.path.join(carpeta, f"{base}_{n}{ext}"), n + 1
    tmp = destino + ".tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(contenido)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, destino)
    except OSError:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return destino
