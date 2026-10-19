"""Plantillas de recetas: platos típicos precargados para agilizar el alta en Mis Recetas."""

PLANTILLAS = [
    {
        "nombre": "Cazuela",
        "precio_venta_sugerido": 6000,
        "mano_obra_sugerida": 500,
        "insumos": [
            {"nombre": "Carne de vacuno", "unidad": "kg", "precio_referencia": 7500, "merma_pct": 8, "cantidad": 0.18},
            {"nombre": "Papa", "unidad": "kg", "precio_referencia": 700, "merma_pct": 10, "cantidad": 0.15},
            {"nombre": "Zapallo", "unidad": "kg", "precio_referencia": 600, "merma_pct": 15, "cantidad": 0.12},
            {"nombre": "Zanahoria", "unidad": "kg", "precio_referencia": 800, "merma_pct": 8, "cantidad": 0.05},
            {"nombre": "Choclo", "unidad": "un", "precio_referencia": 500, "merma_pct": 0, "cantidad": 1},
            {"nombre": "Cebolla", "unidad": "kg", "precio_referencia": 900, "merma_pct": 12, "cantidad": 0.03},
        ],
    },
    {
        "nombre": "Hamburguesa Clásica",
        "precio_venta_sugerido": 4500,
        "mano_obra_sugerida": 800,
        "insumos": [
            {"nombre": "Carne molida", "unidad": "kg", "precio_referencia": 6500, "merma_pct": 5, "cantidad": 0.15},
            {"nombre": "Pan hamburguesa", "unidad": "un", "precio_referencia": 350, "merma_pct": 2, "cantidad": 1},
            {"nombre": "Queso gauda", "unidad": "kg", "precio_referencia": 7800, "merma_pct": 3, "cantidad": 0.03},
            {"nombre": "Tomate", "unidad": "kg", "precio_referencia": 1200, "merma_pct": 10, "cantidad": 0.03},
            {"nombre": "Lechuga", "unidad": "un", "precio_referencia": 900, "merma_pct": 8, "cantidad": 0.2},
        ],
    },
    {
        "nombre": "Papas Fritas",
        "precio_venta_sugerido": 2500,
        "mano_obra_sugerida": 300,
        "insumos": [
            {"nombre": "Papa", "unidad": "kg", "precio_referencia": 700, "merma_pct": 10, "cantidad": 0.3},
            {"nombre": "Aceite", "unidad": "lt", "precio_referencia": 2500, "merma_pct": 1, "cantidad": 0.05},
        ],
    },
    {
        "nombre": "Empanada de Pino",
        "precio_venta_sugerido": 1800,
        "mano_obra_sugerida": 400,
        "insumos": [
            {"nombre": "Carne molida", "unidad": "kg", "precio_referencia": 6500, "merma_pct": 5, "cantidad": 0.08},
            {"nombre": "Cebolla", "unidad": "kg", "precio_referencia": 900, "merma_pct": 12, "cantidad": 0.10},
            {"nombre": "Harina", "unidad": "kg", "precio_referencia": 900, "merma_pct": 2, "cantidad": 0.09},
            {"nombre": "Huevo", "unidad": "un", "precio_referencia": 180, "merma_pct": 0, "cantidad": 0.5},
            {"nombre": "Aceituna", "unidad": "un", "precio_referencia": 60, "merma_pct": 0, "cantidad": 1},
        ],
    },
    {
        "nombre": "Completo Italiano",
        "precio_venta_sugerido": 2200,
        "mano_obra_sugerida": 250,
        "insumos": [
            {"nombre": "Vienesa", "unidad": "un", "precio_referencia": 350, "merma_pct": 0, "cantidad": 1},
            {"nombre": "Pan completo", "unidad": "un", "precio_referencia": 400, "merma_pct": 2, "cantidad": 1},
            {"nombre": "Palta", "unidad": "kg", "precio_referencia": 3500, "merma_pct": 20, "cantidad": 0.05},
            {"nombre": "Tomate", "unidad": "kg", "precio_referencia": 1200, "merma_pct": 10, "cantidad": 0.04},
        ],
    },
]