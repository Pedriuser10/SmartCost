"""Selector de fotos nativo de Android: la galería del sistema, con miniaturas.

No necesita permisos de almacenamiento (Android entrega solo la foto elegida), así que
evita los dos problemas del selector de archivos: listar nombres sin imagen y fallar con
"Permission denied" en fotos de la papelera (.trashed-*) o recién concedido el permiso.
"""
import os
import time

from kivy.clock import mainthread
from kivy.logger import Logger

SOLICITUD_FOTO = 4711
RESULT_OK = -1
TIPOS = {"image/png": ".png", "image/webp": ".webp", "image/jpeg": ".jpg"}

_al_terminar = None
_enlazado = False


def elegir_foto(al_terminar):
    """Abre la galería. Luego llama, en el hilo de Kivy, a al_terminar(nombre, contenido, error):
    con la foto elegida, con todo en None si se canceló, o con error si no se pudo leer."""
    global _al_terminar, _enlazado
    from android import activity
    from jnius import autoclass

    _al_terminar = al_terminar
    if not _enlazado:
        # Se enlaza una sola vez y no se desenlaza dentro de la respuesta: Java recorre la
        # lista de listeners mientras la llama y quitarlo ahí lanzaría ConcurrentModificationException
        activity.bind(on_activity_result=_resultado)
        _enlazado = True
    Intent = autoclass("android.content.Intent")
    if autoclass("android.os.Build$VERSION").SDK_INT >= 33:
        intent = Intent("android.provider.action.PICK_IMAGES")  # selector de fotos del sistema
    else:
        intent = Intent(Intent.ACTION_GET_CONTENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
    intent.setType("image/*")
    autoclass("org.kivy.android.PythonActivity").mActivity.startActivityForResult(intent, SOLICITUD_FOTO)


def _resultado(codigo, resultado, intent):
    if codigo != SOLICITUD_FOTO:
        return
    if resultado != RESULT_OK or intent is None or intent.getData() is None:
        _entregar(None, None, None)  # el usuario volvió sin elegir
        return
    try:
        nombre, contenido = _leer(intent.getData())
    except Exception as e:
        Logger.exception("SmartCost: no se pudo leer la foto elegida")
        _entregar(None, None, str(e))
        return
    _entregar(nombre, contenido, None)


def _leer(uri):
    from jnius import autoclass
    resolver = autoclass("org.kivy.android.PythonActivity").mActivity.getContentResolver()
    nombre = None
    cursor = resolver.query(uri, None, None, None, None)
    if cursor is not None:
        try:
            columna = cursor.getColumnIndex("_display_name")
            if columna >= 0 and cursor.moveToFirst():
                nombre = cursor.getString(columna)
        finally:
            cursor.close()
    if not nombre:
        nombre = time.strftime("foto_%Y%m%d_%H%M%S") + TIPOS.get(resolver.getType(uri) or "", ".jpg")
    # Se lee con Python a partir del descriptor que entrega Android
    descriptor = resolver.openFileDescriptor(uri, "r")
    with os.fdopen(descriptor.detachFd(), "rb") as f:
        return nombre, f.read()


@mainthread
def _entregar(nombre, contenido, error):
    global _al_terminar
    al_terminar, _al_terminar = _al_terminar, None
    if al_terminar is not None:
        al_terminar(nombre, contenido, error)
