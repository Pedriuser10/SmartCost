"""Utilidades de UI compartidas por las vistas (KivyMD 2.0)."""
from kivymd.uix.button import MDButtonText


def alto_segun_texto(etiqueta, minimo=0):
    """La etiqueta toma el alto de su texto (con varias líneas en pantallas angostas),
    para que un contenedor con adaptive_height no la recorte ni la superponga."""
    etiqueta.size_hint_y = None
    etiqueta.bind(texture_size=lambda e, s: setattr(e, "height", max(minimo, s[1])))
    return etiqueta


def alto_segun_contenido(tarjeta):
    """La tarjeta crece o se achica con su contenido.

    No se usa adaptive_height=True en MDCard: en KivyMD 2.0.0 deja el alto en 0 mientras
    la tarjeta no tiene hijos, y el efecto ripple crea entonces un FBO de alto 0 que el
    GPU del teléfono rechaza ("FBO Initialization failed") y la app se cierra al abrir.
    La tarjeta se crea con un alto inicial y luego sigue a minimum_height.
    """
    tarjeta.size_hint_y = None
    tarjeta.bind(minimum_height=tarjeta.setter("height"))
    return tarjeta


def set_texto_boton(boton, texto):
    """En KivyMD 2.0 un MDButton no tiene `.text`: el texto vive en su hijo MDButtonText."""
    for w in boton.walk():
        if isinstance(w, MDButtonText):
            w.text = texto
            return