# SmartCost

App para calcular el costo real de los platos y controlar la rentabilidad del menú en
pequeños negocios gastronómicos. Hecha en Python con Kivy/KivyMD; funciona en el PC
(Linux) y en Android.

Proyecto desarrollado para la asignatura **Desarrollo Móvil (TINF1119V)**,
Evaluación Integrada RA1. Desarrollado en Chile.

> **Estado: en desarrollo.** La app abre y se usa en Android, pero algunas
> funciones están incompletas o tienen limitaciones (ver
> [Limitaciones conocidas](#limitaciones-conocidas)).

## Funcionalidades

| Módulo | Qué hace |
|---|---|
| **Login y registro** | Cuentas locales con contraseña segura (PBKDF2-HMAC-SHA256, sal por usuario, bloqueo temporal tras 5 intentos fallidos) |
| **Mis Recetas** | Alta, edición y borrado (con confirmación) de insumos y platos, foto del plato y los insumos de cada receta |
| **Calcular Costos** | Desglose de un plato: subtotal por insumo, costo real total y margen |
| **Menú** | Carta visual con las fotos de los platos |
| **Ingeniería de Menú** | Ranking de platos por margen, gráfico de barras y semáforo verde/amarillo/rojo |
| **Mis Plantillas** | Recetas típicas precargadas, generador de combinaciones (proteína + guarnición + salsa) e importación desde CSV |
| **Configuración / Acerca de** | Pantallas de relleno, pendientes de desarrollo |

Otros detalles:

- **Fotos:** en Android se eligen desde la galería del sistema (no requiere permisos);
  se enderezan según la orientación de la cámara (EXIF) y se reducen a 1600 px.
- **Botón Atrás de Android:** cierra el diálogo abierto o vuelve al inicio.
- **Datos persistentes:** las cuentas, recetas y fotos se guardan fuera de la carpeta de la
  app, así que se conservan al actualizarla (ver [Dónde se guardan los datos](#dónde-se-guardan-los-datos)).

## Tecnologías

- Python 3, [Kivy](https://kivy.org) 2.3.1 y [KivyMD](https://github.com/kivymd/KivyMD) 2.0.0
- `materialyoucolor` 3.0.4, `asynckivy` 0.6.4, `asyncgui` 0.6.3 (dependencias de KivyMD)
- Pillow (procesamiento de fotos)
- Datos en archivos JSON (sin base de datos externa)
- Android: [Buildozer](https://github.com/kivy/buildozer) 1.6.0 y python-for-android, API 33, arquitectura arm64-v8a

## Estructura del proyecto

```
SmartCost/
├── main.py                      # punto de entrada: tema, migración de datos, pantallas y botón Atrás
├── buildozer.spec               # configuración para compilar el APK
├── requirements.txt             # dependencias para ejecutar en el PC
├── models/                      # datos, sin interfaz
│   ├── rutas.py                 # dónde viven los datos, migración inicial y guardado atómico
│   ├── storage.py               # insumos, platos y recetas (data/app.json)
│   ├── usuarios.py              # cuentas (usuarios.json)
│   └── fotos.py                 # guardado de fotos: EXIF, reducción, nombres sin colisiones
├── services/                    # lógica de negocio pura
│   ├── auth.py                  # registro, login, política de contraseñas, bloqueo
│   ├── calculo_costos.py        # costo real, margen y clasificación
│   ├── plantillas.py            # recetas típicas precargadas
│   └── combinaciones.py         # ingredientes base del generador de combinaciones
├── views/                       # una clase por pantalla (KivyMD 2.0)
│   ├── login_screen.py, home_screen.py, recetas_screen.py, cost_calculator_screen.py,
│   │   menu_visual_screen.py, ingenieria_menu_screen.py, plantillas_screen.py, module_screen.py
│   ├── selector_fotos_android.py  # galería nativa de Android (pyjnius)
│   ├── marca.py                 # paleta y recursos de la identidad visual
│   └── utils.py                 # ayudas de interfaz compartidas
├── widgets/module_card.py       # tarjeta de la pantalla de inicio
├── data/                        # datos de ejemplo que se copian en el primer arranque
│   ├── app.json                 # insumos y platos de ejemplo
│   └── imagenes/                # fotos de ejemplo de los platos
├── recursos/marca/              # fondo del login, símbolo, bandera (generados)
└── herramientas/generar_marca.py  # regenera recursos/marca (no se incluye en el APK)
```

## Ejecutar en el PC

```bash
pip install -r requirements.txt
python main.py
```

En Linux puede hacer falta `xsel` para el portapapeles (`sudo dnf install xsel` en Fedora).

> Nota: la app se ha usado en el PC con KivyMD instalado desde la rama `master` de
> GitHub (2.0.1.dev0) y Python 3.14. La instalación limpia con `pip install -r
> requirements.txt` (KivyMD 2.0.0 de PyPI) no se ha verificado; KivyMD 2.0.0 instala
> también `materialshapes`, que necesita `pycairo` (y las bibliotecas de desarrollo de
> cairo en Linux).

## Compilar el APK para Android

```bash
buildozer android debug
```

El APK queda en `bin/`. Para instalarlo como actualización sin perder los datos del
teléfono: `adb install -r bin/smartcost-1.0-arm64-v8a-debug.apk`.

Notas de la configuración actual (`buildozer.spec`):

- Las versiones de `kivymd`, `materialyoucolor`, `asynckivy` y `asyncgui` están fijadas a
  propósito: con otras combinaciones la app se cerraba al abrir
  (`No module named 'materialyoucolor.dynamiccolor.color_spec'`).
- `data/usuarios.json` se excluye del APK para no empaquetar las cuentas del PC.
- El APK de depuración se firma con la clave debug local; para instalarlo como
  actualización tiene que firmarse con la misma clave que la versión instalada.

## Dónde se guardan los datos

Los datos del usuario se guardan en `<user_data_dir>/datos/`:

- **Android:** `/data/data/cl.uct.smartcost/files/datos/` (privado de la app)
- **Linux:** `~/.config/smartcost/datos/`

En el primer arranque se copian ahí los datos de ejemplo de `data/` (nunca se sobrescribe
un archivo que ya exista). La carpeta de la app no sirve para guardar datos: en Android se
borra y se vuelve a extraer en cada actualización. Si la carpeta de datos no se puede
preparar, la app muestra un error y no lee ni escribe nada, para no crear una base de
cuentas vacía.

`data/usuarios.json` no se versiona (está en `.gitignore`): contiene los hashes de las
contraseñas de las cuentas locales.

## Fórmulas

```
costo_real = Σ(cantidad_insumo × precio_unitario × (1 + merma)) + mano_de_obra
margen %   = ((precio_venta - costo_real) / precio_venta) × 100
```

La cantidad de cada insumo va en la misma unidad en que está su precio.
Clasificación: **> 30 % bueno (verde)**, **10–30 % regular (amarillo)**, **< 10 % malo (rojo)**.

## Importar recetas desde CSV

Una fila por cada insumo de cada plato:

```csv
plato,precio_venta,mano_obra,insumo,unidad,precio,merma_pct,cantidad
Cazuela,6000,500,Carne de vacuno,kg,7500,8,0.18
Cazuela,6000,500,Papa,kg,700,10,0.15
```

También acepta el formato de Excel en español (separador `;` y coma decimal) y archivos
en Latin-1. Si una fila es inválida, indica el número de fila y no importa nada.

## Decisiones de diseño (POO)

- **Separación lógica/interfaz:** `models/` y `services/` no dependen de Kivy y se pueden
  probar con datos puros. Las pantallas de `views/` solo llaman a esas funciones; nunca
  leen ni escriben los JSON directamente.
- **Una clase por pantalla**, heredando de `MDScreen`, cada una dueña de su propio estado
  (por ejemplo, `RecetasScreen` mantiene `self.modo` para alternar entre insumos y platos).
- **`DishCard` y `ModuleCard`** como widgets reutilizables (heredan de `MDCard`), en vez de
  repetir el mismo layout en cada pantalla.
- **Rutas de datos centralizadas** en `models/rutas.py`, con guardado atómico (archivo
  temporal + `os.replace`) para que un cierre inesperado no deje un JSON a medias.

## Pruebas

El repositorio todavía **no incluye pruebas automatizadas**. Durante el desarrollo de
estos avances se usaron, fuera del repositorio:

- pruebas de la migración y la persistencia de datos (migración inicial, segundo arranque
  sin sobrescribir, JSON corruptos, errores de permisos y guardado atómico);
- un recorrido automatizado de la interfaz en el PC que emula la pantalla de un teléfono
  (384 dp), con datos aislados;
- pruebas manuales en un teléfono Android 16 (arm64): arranque, inicio de sesión,
  conservación de datos al actualizar, guardar un plato y elegir una foto de la galería.

## Limitaciones conocidas

- **Importar CSV en Android:** desde Android 13 no se puede leer un CSV de Descargas sin el
  selector de documentos del sistema; por ahora la importación funciona en el PC.
- **Configuración y Acerca de** son pantallas de relleno.
- **Ingeniería de Menú** solo considera el margen; no hay datos de ventas para medir la
  popularidad.
- Usar una plantilla o importar el mismo CSV dos veces crea platos duplicados.
- Los montos se muestran con formato `$2,656` (coma de miles) en vez de `$2.656`.
- Al iniciar sesión la pantalla se detiene uno o dos segundos (cálculo del hash de la
  contraseña en el hilo de la interfaz).
- No hay inicio de sesión con huella digital.
- Si los insumos tienen la cantidad dentro de la unidad (p. ej. precio por «8kg» y cantidad
  1), el costo calculado no es el esperado: conviene registrar el precio por unidad simple.

## Mejoras futuras

- Editar la cantidad de un insumo ya asociado a un plato (hoy solo se puede quitar y volver a agregar)
- Reportes por período y costos fijos prorrateados
- Exportar el dashboard a PDF o Excel
- Desarrollar los módulos de Configuración y Acerca de
