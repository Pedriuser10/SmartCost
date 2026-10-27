"""Utilidades de UI compartidas por las vistas (KivyMD 2.0)."""
from kivymd.uix.button import MDButtonText


def set_texto_boton(boton, texto):
    """En KivyMD 2.0 un MDButton no tiene `.text`: el texto vive en su hijo MDButtonText."""
    for w in boton.walk():
        if isinstance(w, MDButtonText):
            w.text = texto
            return