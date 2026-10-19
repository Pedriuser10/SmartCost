"""
Insumos base para el generador de combinaciones.
Con 8 proteínas x 8 guarniciones x 6 salsas = 384 platos posibles,
manteniendo solo 22 ingredientes base.
"""

PROTEINAS = [
    {"nombre": "Pollo", "unidad": "kg", "precio": 3200, "merma_pct": 10, "cantidad": 0.15},
    {"nombre": "Carne de vacuno", "unidad": "kg", "precio": 7500, "merma_pct": 8, "cantidad": 0.15},
    {"nombre": "Cerdo", "unidad": "kg", "precio": 5200, "merma_pct": 10, "cantidad": 0.15},
    {"nombre": "Pescado (merluza)", "unidad": "kg", "precio": 4800, "merma_pct": 15, "cantidad": 0.18},
    {"nombre": "Pavo", "unidad": "kg", "precio": 4500, "merma_pct": 10, "cantidad": 0.15},
    {"nombre": "Salmón", "unidad": "kg", "precio": 9500, "merma_pct": 12, "cantidad": 0.15},
    {"nombre": "Chuleta de cerdo", "unidad": "kg", "precio": 5800, "merma_pct": 8, "cantidad": 0.18},
    {"nombre": "Longaniza", "unidad": "kg", "precio": 4200, "merma_pct": 5, "cantidad": 0.15},
]

GUARNICIONES = [
    {"nombre": "Papas fritas", "unidad": "kg", "precio": 700, "merma_pct": 10, "cantidad": 0.25},
    {"nombre": "Puré de papas", "unidad": "kg", "precio": 700, "merma_pct": 10, "cantidad": 0.2},
    {"nombre": "Arroz", "unidad": "kg", "precio": 900, "merma_pct": 2, "cantidad": 0.15},
    {"nombre": "Tallarines", "unidad": "kg", "precio": 1200, "merma_pct": 3, "cantidad": 0.15},
    {"nombre": "Ensalada mixta", "unidad": "kg", "precio": 1000, "merma_pct": 10, "cantidad": 0.15},
    {"nombre": "Ensalada a la chilena", "unidad": "kg", "precio": 1100, "merma_pct": 12, "cantidad": 0.15},
    {"nombre": "Puré de zapallo", "unidad": "kg", "precio": 600, "merma_pct": 15, "cantidad": 0.2},
    {"nombre": "Charquicán", "unidad": "kg", "precio": 900, "merma_pct": 10, "cantidad": 0.2},
]

SALSAS = [
    {"nombre": "Sin salsa", "unidad": "porción", "precio": 0, "merma_pct": 0, "cantidad": 0},
    {"nombre": "A lo pobre (huevo+cebolla)", "unidad": "porción", "precio": 400, "merma_pct": 0, "cantidad": 1},
    {"nombre": "Salsa churrasca", "unidad": "porción", "precio": 250, "merma_pct": 0, "cantidad": 1},
    {"nombre": "Salsa de champiñones", "unidad": "porción", "precio": 350, "merma_pct": 0, "cantidad": 1},
    {"nombre": "Pebre", "unidad": "porción", "precio": 200, "merma_pct": 0, "cantidad": 1},
    {"nombre": "Salsa a la pimienta", "unidad": "porción", "precio": 380, "merma_pct": 0, "cantidad": 1},
]