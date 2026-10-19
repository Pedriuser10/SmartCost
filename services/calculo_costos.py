"""Lógica de negocio pura: costo real, margen y clasificación de rentabilidad."""


def costo_real_plato(insumos_usados, costo_mano_obra=0):
    total = 0.0
    for item in insumos_usados:
        total += item["cantidad"] * item["precio"] * (1 + item.get("merma_pct", 0))
    return round(total + costo_mano_obra, 2)


def margen(precio_venta, costo_real):
    if precio_venta <= 0:
        return 0.0
    return round(((precio_venta - costo_real) / precio_venta) * 100, 2)


def clasificar_margen(margen_pct):
    if margen_pct > 30:
        return "bueno"
    elif margen_pct >= 10:
        return "regular"
    else:
        return "malo"


COLOR_MARGEN = {
    "bueno": (0.29, 0.68, 0.31, 1),
    "regular": (0.95, 0.73, 0.13, 1),
    "malo": (0.83, 0.24, 0.24, 1),
}