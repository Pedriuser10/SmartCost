"""Genera los recursos gráficos de la identidad de SmartCost (originales, sin imágenes externas).

    python3 herramientas/generar_marca.py

Crea en recursos/marca/:
- fondo_login.jpg  cordillera de los Andes al anochecer, 1080x2400 (pantalla del teléfono)
- logo.png         símbolo: cumbres andinas sobre un plato, con la cresta como línea de datos
- icono.png        ícono de la app (logo sobre fondo, 512x512)
- presplash.png    logo para la pantalla de carga
- bandera_chile.png  bandera pequeña para «Desarrollado en Chile»

Se generan con una semilla fija: volver a ejecutarlo produce los mismos archivos.
Esta carpeta no se empaqueta en el APK (ver source.exclude_dirs en buildozer.spec).
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "recursos", "marca")

# Paleta de marca (misma que views/marca.py)
AZUL_NOCHE = (8, 24, 48)        # #081830
AZUL_OSCURO = (11, 31, 58)      # #0B1F3A
AZUL_ANDES = (19, 49, 92)       # #13315C
TURQUESA = (27, 176, 166)       # #1BB0A6  acento SmartCost
TURQUESA_OSCURO = (14, 124, 123)  # #0E7C7B  (texto blanco encima con buen contraste)
ROJO_CHILE = (213, 43, 30)      # #D52B1E
AZUL_BANDERA = (0, 57, 166)     # #0039A6
BLANCO = (255, 255, 255)

ANCHO, ALTO = 1080, 2400


def mezcla(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def cordillera(rng, ancho, base, amplitud, rugosidad, picos):
    """Silueta de montañas por desplazamiento de punto medio, con algunos picos marcados."""
    n = 2 ** 8
    alturas = [0.0] * (n + 1)
    paso, escala = n, amplitud
    while paso > 1:
        mitad = paso // 2
        for i in range(mitad, n, paso):
            alturas[i] = (alturas[i - mitad] + alturas[i + mitad]) / 2 + rng.uniform(-escala, escala)
        escala *= rugosidad
        paso = mitad
    for centro, alto, ancho_pico in picos:  # cumbres destacadas (estilo Torres / volcanes)
        for i in range(n + 1):
            d = abs(i / n - centro) / ancho_pico
            if d < 1:
                alturas[i] += alto * (1 - d) ** 1.6
    return [(i * ancho / n, base - h) for i, h in enumerate(alturas)]


def fondo():
    rng = random.Random(1810)  # semilla fija
    img = Image.new("RGB", (ANCHO, ALTO))
    d = ImageDraw.Draw(img)
    # Cielo: noche andina que se aclara hacia el horizonte, con un leve tono turquesa
    for y in range(ALTO):
        t = y / ALTO
        if t < 0.62:
            color = mezcla(AZUL_NOCHE, AZUL_ANDES, t / 0.62)
        else:
            color = mezcla(AZUL_ANDES, mezcla(AZUL_ANDES, TURQUESA_OSCURO, 0.45), (t - 0.62) / 0.38)
        d.line([(0, y), (ANCHO, y)], fill=color)

    # Estrellas tenues (cielo del norte de Chile), solo en la parte alta
    estrellas = Image.new("L", (ANCHO, ALTO), 0)
    de = ImageDraw.Draw(estrellas)
    for _ in range(140):
        x, y = rng.uniform(0, ANCHO), rng.uniform(0, ALTO * 0.5) ** 1.08
        r = rng.choice([1, 1, 1, 1.5, 2])
        de.ellipse([x - r, y - r, x + r, y + r], fill=rng.randint(40, 130))
    img.paste(BLANCO, (0, 0), estrellas)

    # Tres cordones de montañas: el del fondo con nieve, el del frente casi negro azulado
    capas = [
        # (línea base, amplitud del relieve, rugosidad, cumbres (centro, alto, ancho), color, nieve)
        (ALTO * 0.71, 150, 0.50, [(0.24, 210, 0.22), (0.64, 260, 0.20), (0.90, 150, 0.16)],
         mezcla(AZUL_ANDES, TURQUESA_OSCURO, 0.12), True),
        (ALTO * 0.80, 110, 0.48, [(0.42, 150, 0.26), (0.95, 110, 0.20)], mezcla(AZUL_OSCURO, AZUL_ANDES, 0.45), False),
        (ALTO * 0.89, 70, 0.46, [(0.10, 90, 0.28), (0.72, 70, 0.25)], AZUL_NOCHE, False),
    ]
    for base, amp, rug, picos, color, nieve in capas:
        perfil = cordillera(rng, ANCHO, base, amp, rug, picos)
        poligono = perfil + [(ANCHO, ALTO), (0, ALTO)]
        capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
        dc = ImageDraw.Draw(capa)
        dc.polygon(poligono, fill=color + (255,))
        if nieve:
            # Nieve: solo sobre lo que sube por encima de cierta altura, con bordes suaves
            limite = base - amp * 1.25
            mascara = Image.new("L", (ANCHO, ALTO), 0)
            ImageDraw.Draw(mascara).polygon(poligono, fill=255)
            corte = Image.new("L", (ANCHO, ALTO), 0)
            ImageDraw.Draw(corte).rectangle([0, 0, ANCHO, limite], fill=255)
            corte = corte.filter(ImageFilter.GaussianBlur(40))
            nieve_m = Image.composite(corte, Image.new("L", (ANCHO, ALTO), 0), mascara)
            nieve_m = nieve_m.point(lambda v: int(v * 0.42))
            capa.paste(mezcla(BLANCO, TURQUESA, 0.08) + (255,), (0, 0), nieve_m)
        img.paste(capa, (0, 0), capa)

    # Grano muy leve para evitar bandas en el degradado al comprimir
    ruido = Image.effect_noise((ANCHO, ALTO), 6).convert("L")
    img = Image.blend(img, Image.merge("RGB", (ruido, ruido, ruido)), 0.025)
    img.save(os.path.join(SALIDA, "fondo_login.jpg"), "JPEG", quality=82, optimize=True, progressive=True)


def logo(tam=512, con_fondo=True):
    """Cumbres andinas sobre un plato; la cresta es una línea de datos y la estrella es chilena."""
    s = 4  # supermuestreo para bordes suaves
    T = tam * s
    img = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if con_fondo:
        d.rounded_rectangle([0, 0, T - 1, T - 1], radius=T * 0.22, fill=AZUL_OSCURO + (255,))
    u = T / 100  # unidades de 0 a 100
    # Plato hondo: arco bajo las montañas (gastronomía)
    d.arc([12 * u, 40 * u, 88 * u, 84 * u], start=8, end=172, fill=BLANCO + (255,), width=round(4 * u))
    # Montañas dentro del plato: la de atrás turquesa, la de adelante blanca
    d.polygon([(20 * u, 64 * u), (42 * u, 28 * u), (64 * u, 64 * u)], fill=TURQUESA + (255,))
    d.polygon([(40 * u, 64 * u), (60 * u, 38 * u), (80 * u, 64 * u)], fill=BLANCO + (255,))
    # Línea de datos que une las cumbres y sube (tecnología / costos)
    puntos = [(42 * u, 28 * u), (60 * u, 38 * u), (82 * u, 20 * u)]
    d.line(puntos, fill=TURQUESA + (255,), width=round(3.2 * u), joint="curve")
    for x, y in puntos:
        r = 3.4 * u
        d.ellipse([x - r, y - r, x + r, y + r], fill=BLANCO + (255,), outline=TURQUESA + (255,), width=round(1.6 * u))
    # Estrella roja pequeña (Chile)
    estrella(d, (24 * u, 24 * u), 7 * u, ROJO_CHILE)
    return img.resize((tam, tam), Image.LANCZOS)


def estrella(d, centro, radio, color):
    cx, cy = centro
    puntos = []
    for i in range(10):
        r = radio if i % 2 == 0 else radio * 0.40
        a = -math.pi / 2 + i * math.pi / 5
        puntos.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(puntos, fill=color + (255,))


def bandera(ancho=96):
    """Bandera de Chile en proporción 3:2."""
    s = 4
    W, H = ancho * s, ancho * s * 2 // 3
    img = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H // 2], fill=BLANCO + (255,))
    d.rectangle([0, H // 2, W, H], fill=ROJO_CHILE + (255,))
    d.rectangle([0, 0, H // 2, H // 2], fill=AZUL_BANDERA + (255,))
    estrella(d, (H / 4, H / 4), H * 0.15, BLANCO)
    img = img.resize((ancho, ancho * 2 // 3), Image.LANCZOS)
    redondeo = Image.new("L", img.size, 0)
    ImageDraw.Draw(redondeo).rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=6, fill=255)
    img.putalpha(redondeo)
    return img


if __name__ == "__main__":
    os.makedirs(SALIDA, exist_ok=True)
    fondo()
    logo(256).save(os.path.join(SALIDA, "logo.png"), optimize=True)
    logo(512).save(os.path.join(SALIDA, "icono.png"), optimize=True)
    # Pantalla de carga: Android la escala al ancho de la pantalla y la guarda como JPEG,
    # así que va sobre fondo azul y con el símbolo ocupando solo un tercio del ancho
    carga = Image.new("RGB", (1080, 1080), AZUL_OSCURO)
    simbolo = logo(360, con_fondo=False)
    carga.paste(simbolo, ((1080 - 360) // 2, (1080 - 360) // 2), simbolo)
    carga.save(os.path.join(SALIDA, "presplash.png"), optimize=True)
    bandera().save(os.path.join(SALIDA, "bandera_chile.png"), optimize=True)
    for nombre in sorted(os.listdir(SALIDA)):
        ruta = os.path.join(SALIDA, nombre)
        with Image.open(ruta) as im:
            print(f"{nombre:20s} {im.size[0]}x{im.size[1]:<5d} {os.path.getsize(ruta) / 1024:7.1f} KB")
