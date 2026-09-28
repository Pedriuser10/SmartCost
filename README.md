# SmartCost

App para calcular costos reales y controlar la rentabilidad del menú en
pequeños negocios gastronómicos. Python + Kivy/KivyMD + SQLite.

Proyecto desarrollado para la asignatura **Desarrollo Móvil (TINF1119V)**,
Evaluación Integrada RA1.

## Instalación

```bash
pip install -r requirements.txt
sudo dnf install xsel   # Linux: evita un warning del portapapeles al abrir
```

## Ejecutar

```bash
python main.py
```

La primera vez se crea `data/app.db` (SQLite) con datos de ejemplo
(insumos y platos ya cargados) para poder probar la app sin ingresar
todo a mano.

## Estructura del proyecto

```
SmartCost/
├── main.py                        # punto de entrada: arma el ScreenManager y el tema
├── lib/                            # lógica de negocio, sin interfaz
│   ├── storage.py                  # acceso a SQLite (CRUD de insumos, platos, receta)
│   ├── calculo_costos.py           # fórmulas: costo real, margen, clasificación
│   ├── plantillas.py               # recetas típicas precargadas
│   └── combinaciones.py            # ingredientes base para el generador de combos
├── screens/
│   ├── home_screen.py              # pantalla de inicio (grid de 6 tarjetas)
│   ├── module_screen.py            # pantalla base placeholder (Config, Acerca de)
│   ├── recetas_screen.py           # "Mis Recetas": CRUD insumos + platos + fotos
│   ├── cost_calculator_screen.py   # "Calcular Costos": desglose real de un plato
│   ├── ingenieria_menu_screen.py   # "Ingeniería de Menú": ranking de rentabilidad
│   ├── menu_visual_screen.py       # "Menú": carta visual estilo app de comida rápida
│   └── plantillas_screen.py        # "Mis Plantillas": generador + importador CSV
├── widgets/
│   └── module_card.py              # tarjeta reutilizable de la pantalla de inicio
├── data/
│   ├── app.db                      # base de datos SQLite (se crea sola)
│   └── images/                     # fotos de platos (se crean solas al elegir una)
├── requirements.txt
└── README.md
```

## Base de datos

SQLite (módulo estándar `sqlite3`, sin dependencias externas), 3 tablas:

- **`insumos`** — ingredientes: nombre, unidad, precio de compra, % de merma
- **`platos`** — productos del menú: nombre, precio de venta, mano de obra, foto
- **`plato_insumos`** — tabla puente: qué insumos y en qué cantidad usa cada plato

## Módulos de la app

| Módulo | Qué hace |
|---|---|
| **Calcular Costos** | Eliges un plato ya cargado y ves el desglose real: cada insumo con su subtotal, costo total y margen |
| **Menú** | Carta visual con fotos de tus platos, estilo app de comida rápida |
| **Ingeniería de Menú** | Ranking de todos tus platos por rentabilidad, con semáforo verde/amarillo/rojo |
| **Mis Recetas** | CRUD de insumos y platos, con selector de foto y asociación de ingredientes a cada receta |
| **Mis Plantillas** | 3 formas de cargar recetas rápido: plantillas fijas, generador de combinaciones (proteína + guarnición + salsa), e importación masiva desde CSV |
| **Configuración** / **Acerca de** | Pantallas placeholder, pendientes de desarrollo |

## Fórmulas clave

```
costo_real = Σ(cantidad_insumo × precio_unitario × (1 + merma)) + mano_de_obra
margen %   = ((precio_venta - costo_real) / precio_venta) × 100
```

Clasificación de rentabilidad: **>30% = bueno (verde)**, **10-30% = regular (amarillo)**, **<10% = malo (rojo)**.

## Importar recetas desde CSV

Formato esperado (una fila por cada insumo de cada plato):

```csv
plato,precio_venta,mano_obra,insumo,unidad,precio,merma_pct,cantidad
Cazuela,6000,500,Carne de vacuno,kg,7500,8,0.18
Cazuela,6000,500,Papa,kg,700,10,0.15
Lasaña,5500,600,Carne molida,kg,6500,5,0.2
```

## Decisiones de diseño (POO)

- **Separación lógica/interfaz**: `lib/` no depende de Kivy — se puede probar
  con datos puros. Las `screens/` solo llaman a esas funciones, nunca
  ejecutan SQL directamente.
- **Una clase por pantalla**, heredando de `MDScreen`, cada una dueña de
  su propio estado (ej. `RecetasScreen` mantiene `self.modo` para alternar
  entre insumos y platos).
- **`DishCard` y `ModuleCard`** como widgets reutilizables (heredan de
  `MDCard`), en vez de repetir el mismo layout en cada pantalla.

## Pendiente / mejoras futuras

- Editar la cantidad de un insumo ya asociado a un plato (hoy solo se puede quitar y volver a agregar)
- Reportes por período y costos fijos prorrateados
- Exportar el dashboard a PDF o Excel
- Desarrollar los módulos de Configuración y Acerca de nosotros
  
