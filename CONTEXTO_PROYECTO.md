# Contexto del proyecto SmartCost

Documento de referencia para retomar el desarrollo (personas o asistentes de IA).
Describe reglas, arquitectura y estado **verificado** del proyecto. Lo que no se pudo
comprobar está marcado como **pendiente de confirmar**.

Última revisión: 2026-10-29, sobre la rama `avance/smartcost-octubre-2026` (commit `432999d`).
Ampliado el 2026-11-26 con las decisiones de inventario y costos (sección 8.14).

---

## 1. Descripción

SmartCost es una aplicación para Android y escritorio que ayuda a pequeños negocios
gastronómicos a gestionar insumos, recetas y platos, y a calcular costos reales,
márgenes y rentabilidad del menú.

| Dato | Valor |
|---|---|
| Lenguaje | Python 3 |
| Interfaz | Kivy 2.3.1 + KivyMD 2.0.0 |
| Compilación Android | Buildozer + python-for-android |
| Paquete Android | `cl.uct.smartcost` (`package.domain = cl.uct`, `package.name = smartcost`) |
| Versión de la app | `1.0` (`buildozer.spec`) |
| Android | `android.api = 33`, `android.minapi = 24`, arquitectura `arm64-v8a` |
| Repositorio | https://github.com/Pedriuser10/SmartCost |
| Rama de avances | `avance/smartcost-octubre-2026` |

---

## 2. Reglas críticas de Git

1. **No modificar `main` directamente.** Todo cambio va en una rama propia y se propone
   mediante Pull Request.
2. **No integrar el commit `fe5204e`** ("Actualizacion de Erroren de visualizacion de
   miniaturas") ni cambios derivados de él sin autorización explícita del autor del
   proyecto.
   - Ese commit **ya está en `origin/main`** (subido directamente a `main`). No está en
     `avance/smartcost-octubre-2026`.
   - Modifica `views/recetas_screen.py` (también modificado en la rama de avances) y
     agrega `data/images/LomoALoPobre.png`.
   - Consecuencia: un PR de la rama de avances hacia `main` chocará con ese commit.
     Decidir cómo tratarlo **antes** de abrir el PR (pendiente de decisión).
3. **Nunca** ejecutar `push`, `commit`, `merge`, `rebase`, `reset --hard`, `checkout --`,
   `clean -f`, `push --force` ni otra operación destructiva sin autorización.
4. **No borrar ni sobrescribir copias de seguridad.**
5. **No subir al repositorio:** `data/usuarios.json`, credenciales, claves de firma
   (`*.keystore`, `*.jks`), archivos `.env`, APK/AAB, `bin/`, `.buildozer/`, `build.log`,
   respaldos ni datos reales del teléfono. El `.gitignore` actual ya excluye todo eso.
6. **Antes de cada tarea:** revisar `git status`, la rama actual y `git log`; si hay
   cambios locales, protegerlos (preguntar antes de tocarlos).

---

## 3. Arquitectura

```
SmartCost/
├── main.py                  # arranque: configura datos, registra pantallas, botón Atrás
├── buildozer.spec           # compilación Android
├── requirements.txt         # dependencias de escritorio
├── models/                  # datos, sin interfaz
│   ├── rutas.py             # ubicación de datos, migración inicial, escritura atómica
│   ├── storage.py           # CRUD de insumos, platos y recetas sobre app.json
│   ├── usuarios.py          # lectura/escritura de usuarios.json
│   └── fotos.py             # enderezar, reducir y guardar fotos sin pisar otras
├── services/                # lógica de negocio
│   ├── auth.py              # registro/login (PBKDF2-SHA256, 600.000 iteraciones, bloqueo)
│   ├── calculo_costos.py    # costo real y margen
│   ├── combinaciones.py     # insumos base del generador de combos (proteína + guarnición + salsa)
│   └── plantillas.py        # recetas típicas predefinidas
├── views/                   # pantallas KivyMD
│   ├── login_screen.py, home_screen.py, recetas_screen.py,
│   ├── cost_calculator_screen.py, ingenieria_menu_screen.py,
│   ├── menu_visual_screen.py, plantillas_screen.py (plantillas + importador CSV),
│   ├── module_screen.py     # pantalla genérica de relleno (Configuración, Acerca de)
│   ├── selector_fotos_android.py  # galería nativa de Android
│   ├── marca.py, utils.py
├── widgets/module_card.py   # tarjetas del menú principal
├── data/                    # datos INICIALES (semilla), no los del usuario
│   ├── app.json             # ejemplo: 14 insumos, 3 platos
│   └── imagenes/            # fotos de ejemplo
├── recursos/marca/          # logo, ícono, presplash, fondo del login
└── herramientas/generar_marca.py  # genera los recursos de marca (no va en el APK)
```

No existe carpeta `tests/` en el repositorio.

### 3.1 Almacenamiento persistente

- Los datos del usuario **no** se guardan en `data/` del proyecto, sino en
  `<user_data_dir>/datos/` (`models/rutas.py`):
  - **Android:** `/data/data/cl.uct.smartcost/files/datos/` (privado de la app). Confirmado
    por la estructura de los respaldos del teléfono (`files/datos/...`).
  - **Linux (escritorio):** `~/.config/smartcost/datos/` (según README; pendiente de
    confirmar en cada equipo).
- Contenido: `app.json` (insumos, platos, recetas), `usuarios.json` (cuentas, permisos
  600) e `imagenes/` (fotos).
- **Migración inicial** (`rutas.migrar()`, llamada en `main.py`): copia `data/app.json`,
  `data/usuarios.json` (si existe) y las fotos de ejemplo **solo si no existen en el
  destino**. Nunca sobrescribe datos del usuario; valida el JSON del origen y de la copia.
- Si la carpeta de datos no se puede preparar, la app muestra una pantalla de error y
  **no lee ni escribe nada** (evita crear una base de cuentas vacía).
- Escritura atómica: se escribe `archivo.tmp`, `fsync`, y luego `os.replace` sobre el
  original (`rutas.escribir_atomico`).
- Motivo: en Android la carpeta de la app (`files/app/`) se borra y se vuelve a extraer en
  cada actualización; `files/datos/` sobrevive.

### 3.2 Fotografías

- **Android:** `views/selector_fotos_android.py` abre el selector nativo del sistema
  (`android.provider.action.PICK_IMAGES` en Android 13+, `ACTION_GET_CONTENT` en
  versiones anteriores). No requiere permisos de almacenamiento: lee la foto elegida a
  través del `ContentResolver`.
- `models/fotos.py` corrige la orientación EXIF, reduce a un lado máximo de 1600 px y
  guarda en `<datos>/imagenes/` sin pisar otra foto (`nombre_1.jpg`, `nombre_2.jpg`...;
  reutiliza la existente si es idéntica).
- En `app.json` se guarda solo el nombre del archivo; `storage.ruta_imagen()` lo busca
  primero en las fotos del usuario y luego en las de ejemplo.

---

## 4. Estado funcional

### 4.1 Implementado (según el código)

- Login y registro con hash PBKDF2 y bloqueo por intentos (`services/auth.py`).
- CRUD de insumos, platos y recetas; agregar y quitar insumos de una receta.
- Calculadora de costos y márgenes; ingeniería de menú con gráfico dibujado en el canvas
  de Kivy (ya no usa matplotlib).
- Plantillas de recetas típicas, generador de combos e importador CSV (escritorio).
- Menú visual con fotos; selector de fotos nativo en Android.
- Persistencia en `user_data_dir` con migración segura.

"Implementado" no significa "probado de punta a punta": ver sección 5.

### 4.2 Pendiente o por verificar (no resuelto)

| # | Tema | Situación verificada en el código |
|---|---|---|
| 1 | Prevención de platos duplicados | `storage.add_plato()` no comprueba nombres; importar el mismo CSV o aplicar la misma plantilla dos veces duplica platos. Los insumos sí se reutilizan por nombre. |
| 2 | Edición de cantidad de un ingrediente en una receta | No existe: solo `add_insumo_a_plato` y `quitar_insumo_de_plato`. |
| 3 | Importación CSV en Android | `plantillas_screen.py` usa `MDFileManager` abierto en `~`; en Android no da acceso práctico a Descargas. Falta un selector nativo (como el de fotos). |
| 4 | Formato chileno de montos (`$2.656`) | 7 lugares usan `:,.0f` (muestra `$2,656`) en `cost_calculator_screen.py`, `menu_visual_screen.py`, `ingenieria_menu_screen.py` y `plantillas_screen.py`. |
| 5 | Auditoría de costos, unidades, rendimientos y márgenes | Pendiente. La cantidad debe ir en la misma unidad que el precio del insumo; no hay conversión de unidades ni concepto de rendimiento/porciones verificado. |
| 6 | Rendimiento del inicio de sesión | Sin medir. Sospecha: 600.000 iteraciones de PBKDF2 en el hilo de la interfaz pueden congelar la pantalla en el teléfono. |
| 7 | Pruebas automáticas permanentes en `tests/` | No existen. |
| 8 | Instalación limpia en entorno virtual nuevo | No verificada (el README advierte que KivyMD 2.0.0 de PyPI arrastra `materialshapes` → `pycairo`). |
| 9 | Pantallas Configuración y Acerca de | Son `ModuleScreen` de relleno, sin funcionalidad. |
| 10 | Autenticación biométrica | No implementada. |

---

## 5. Pruebas

### 5.1 Realizadas (antecedentes)

| Prueba | Dónde | Evidencia |
|---|---|---|
| Elegir foto desde la galería y verla en el menú visual | Teléfono | Confirmado manualmente por el autor. |
| 19 pruebas de persistencia | PC | Informadas en una sesión anterior; **los scripts no están en Git**, no se pueden repetir tal cual. |
| 19 pasos de comprobación funcional | PC | Igual que la anterior: antecedente sin script guardado. |

### 5.2 Faltantes

- Recorrido funcional completo en el teléfono (login, recetas, costos, ingeniería de
  menú, plantillas, CSV, fotos).
- Actualizar la app en el teléfono (`adb install -r`) y comprobar que se conservan
  cuentas, recetas y fotos.
- Importación CSV en el teléfono.
- Tiempo de inicio de sesión en el teléfono.
- Instalación limpia en un entorno virtual nuevo.
- Pruebas automáticas reproducibles en `tests/`.

---

## 6. Compilación, instalación y respaldos

### 6.1 Ejecutar en el PC

```bash
pip install -r requirements.txt
python main.py
```

### 6.2 Compilar e instalar el APK

```bash
buildozer android debug
adb install -r bin/smartcost-1.0-arm64-v8a-debug.apk
```

- `-r` instala como actualización y conserva los datos. **Nunca** desinstalar la app
  antes de respaldar: desinstalar borra `/data/data/cl.uct.smartcost/`.
- La actualización solo funciona si el APK se firma con la misma clave debug que la
  versión instalada.
- `buildozer.spec` excluye `data/usuarios.json`, `tests/`, `herramientas/` y los gráficos
  antiguos del APK.

### 6.3 Respaldo de datos del teléfono

Respaldos existentes en `<carpeta_de_respaldos>/`: una carpeta local del autor, fuera del
repositorio, cuya ruta no se publica. **No borrar ni reemplazar ninguno.**

| Respaldo | Tamaño de `files.tar` | Suma SHA-256 (2026-10-29) |
|---|---|---|
| Respaldo 1 (`telefono_<fecha>_<hora>`) | ~41 MB | coincide |
| Respaldo 2 | ~43 MB | coincide |
| Respaldo 3 | ~43 MB | coincide |
| Respaldo 4 | ~53 MB | coincide |
| Respaldo 5 | ~53 MB | coincide |

Cada respaldo contiene `files.tar` (la carpeta `files/` de la app, incluida
`files/datos/`), su `files.tar.sha256` y sumas de los datos antes del respaldo.

Procedimiento antes de tocar almacenamiento, migraciones o reinstalar:

1. Crear una carpeta **nueva** con fecha y hora; nunca reutilizar una existente.
2. Copiar la carpeta `files/` de la app desde el teléfono. Con un APK debug suele usarse:
   ```bash
   # Sustituir <carpeta_de_respaldos> por la carpeta local de respaldos (fuera del repositorio)
   D="<carpeta_de_respaldos>/telefono_$(date +%Y%m%d_%H%M%S)"
   mkdir "$D"
   adb exec-out run-as cl.uct.smartcost tar -cf - files > "$D/files.tar"
   ```
   **Pendiente de confirmar:** el comando exacto usado para los respaldos anteriores no
   quedó registrado.
3. Verificar: `sha256sum files.tar > files.tar.sha256`, `tar -tf files.tar | grep datos/`
   y comprobar que aparecen `app.json`, `usuarios.json` e `imagenes/`.
4. Solo entonces continuar con el cambio.

---

## 7. Prioridades

Ordenadas por riesgo para los datos y luego por impacto en el uso. Ninguna está
implementada todavía.

1. **Procedimiento de respaldo confirmado y repetible** (sección 6.3), antes de cualquier
   cambio en almacenamiento.
2. **Prevención de platos duplicados** (CSV y plantillas): corrompe los datos del usuario.
3. **Edición de cantidades en recetas**: hoy obliga a borrar y volver a agregar, con
   riesgo de errores.
4. **Auditoría de costos, unidades y márgenes**: un cálculo erróneo invalida el propósito
   de la app. Ver el riesgo prioritario de la sección 8.9 (unidad y envase mezclados).
5. **Pruebas automáticas en `tests/`** para persistencia y cálculos, que protejan los
   puntos 2–4.
6. **Decisión sobre `fe5204e` en `main`** antes de abrir el PR de la rama de avances.
7. **Importación CSV en Android** con selector nativo.
8. **Rendimiento del inicio de sesión** (medir y, si hace falta, ejecutar el hash fuera
   del hilo de la interfaz).
9. **Formato chileno de montos** (`$2.656`) con una única función compartida.
10. **Instalación limpia** en entorno virtual nuevo.
11. **Pantallas Configuración y Acerca de.**
12. **Autenticación biométrica** (opcional).

---

## 8. Decisiones de arquitectura Supabase

Diseño de una arquitectura offline-first: SQLite local como base operativa, cola local de
operaciones pendientes, Supabase Auth, PostgreSQL con RLS y Supabase Storage privado para
fotos. **Nada de esto está implementado.** Esta sección registra lo decidido para guiar
las fases siguientes.

Actualización 2026-11-26: el esquema de PostgreSQL, la base SQLite local con su cola y el
inventario están **escritos y probados** (PR #6, sección 8.14), pero no aplicados en ningún
proyecto Supabase ni conectados a la app. La app sigue usando los JSON.

Convención usada en esta sección:

- **Aprobado:** decisión explícita del autor del proyecto.
- **Requisito futuro:** obligación aprobada que deberá cumplir la implementación; todavía
  no existe en el código.
- **Propuesta:** recomendación técnica aún no aprobada.
- **Pendiente:** cuestión abierta sin decisión.

Las decisiones D1–D7 fueron aprobadas el 2026-10-29. El mismo día se aprobaron tres
ampliaciones, documentadas dentro de la decisión a la que pertenecen: D1.1 (precios de
compra del editor, en 8.1), D7.1 (apertura y uso sin conexión, en 8.7) y D7.2 (resolución
manual de conflictos, en 8.7).

### 8.1 D1. Roles y permisos (aprobado)

- Roles por negocio: `propietario`, `administrador`, `editor` y `lector`.
- Un usuario puede pertenecer a varios negocios, con un rol distinto en cada uno.
- La autorización se verifica en la aplicación **y** en Supabase (políticas RLS,
  restricciones y triggers). La interfaz nunca es el único control.
- Resumen de los roles:
  - `propietario`: control total; administra miembros y permisos; puede transferir la
    propiedad mediante un procedimiento explícito; las acciones destructivas sobre el
    negocio están protegidas.
  - `administrador`: gestiona insumos, platos y recetas; gestiona miembros y permisos
    dentro de los límites que defina el propietario; no puede transferir la propiedad ni
    eliminar o reemplazar al propietario.
  - `editor`: crea y modifica insumos, platos y recetas; registra, crea y actualiza los
    precios de compra de los insumos (D1.1); no administra miembros; sus eliminaciones
    respetan las reglas de integridad y recuperación.
  - `lector`: solo consulta la información autorizada.
- Protecciones obligatorias:
  - Todo negocio conserva **al menos un propietario**.
  - Nadie puede asignarse ni asignar el rol `propietario` fuera del procedimiento de
    transferencia (protección contra escalada de privilegios).
  - El rol `lector` no tiene ninguna política de escritura.

**D1.1. Precios de compra del editor (aprobado, 2026-10-29)**

- El `editor` puede registrar, crear y actualizar los precios de compra de los insumos de
  su negocio, además de las operaciones que ya le permite D1.
- Solo dentro de los negocios en los que es miembro con rol `editor` o superior: el
  aislamiento entre negocios se mantiene.
- No implica ningún permiso para gestionar usuarios, cambiar roles ni administrar el
  negocio.

**Matriz de permisos.** ✅ aprobado · ❌ prohibido (aprobado) · ➜ derivado de lo aprobado,
falta confirmarlo · ⏳ pendiente.

| Operación | Propietario | Administrador | Editor | Lector |
|---|---|---|---|---|
| Ver datos del negocio | ✅ | ✅ | ✅ | ✅ |
| Editar nombre o moneda del negocio | ✅ | ⏳ | ❌ ➜ | ❌ |
| Archivar o eliminar el negocio | ✅ protegido (procedimiento ⏳) | ❌ | ❌ | ❌ |
| Transferir la propiedad | ✅ explícito (procedimiento ⏳) | ❌ | ❌ | ❌ |
| Ver la lista de miembros | ✅ | ✅ | ⏳ | ⏳ |
| Invitar o agregar miembros | ✅ | ✅ dentro de sus límites (¿puede crear administradores? ⏳) | ❌ | ❌ |
| Cambiar roles | ✅ | editores y lectores ➜; otros administradores ⏳ | ❌ | ❌ |
| Quitar miembros | ✅ | editores y lectores ➜; otros administradores ⏳; al propietario ❌ | ❌ | ❌ |
| Salir del negocio | solo tras transferir la propiedad ➜ | ⏳ | ⏳ | ⏳ |
| Límites del administrador (fijos o configurables) | ⏳ | — | — | — |
| Ver insumos, platos y recetas | ✅ | ✅ | ✅ | ✅ |
| Crear insumos, platos y recetas | ✅ | ✅ | ✅ | ❌ |
| Modificar insumos, platos y recetas | ✅ | ✅ | ✅ | ❌ |
| Eliminar (borrado lógico) | ✅ | ✅ | ⏳ | ❌ |
| Restaurar registros eliminados | ⏳ | ⏳ | ⏳ | ❌ |
| Eliminación definitiva | ❌ desde la app; solo limpieza en servidor (plazo ⏳) | ❌ | ❌ | ❌ |
| Importar CSV o aplicar plantillas | ✅ | ✅ | ✅ ➜ | ❌ |
| Registrar, crear y actualizar precios de compra de insumos (D1.1) | ✅ | ✅ | ✅ | ❌ |
| Subir o cambiar la foto de un plato | ✅ | ✅ | ✅ ➜ | ❌ |
| Ver costos y márgenes | ✅ | ✅ | ✅ ➜ | ⏳ |
| Resolver conflictos de sincronización | ✅ | ✅ | ⏳ | ❌ |
| Asignar los datos locales antiguos a un negocio | ⏳ (propuesta: solo propietario) | ⏳ | ❌ | ❌ |
| Gestionar unidades personalizadas | ⏳ | ⏳ | ❌ ➜ | ❌ |

Si se decide que el `lector` no ve costos, RLS no basta (filtra filas, no columnas):
haría falta una vista o función específica (propuesta).

### 8.2 D2. Menús en una fase posterior (aprobado)

- La primera fase **no** crea tablas ni pantallas de menús.
- Alcance de la primera fase: insumos, platos, relaciones de recetas (ingredientes),
  cálculo de costos y márgenes, unidades, fotos, membresías, roles y sincronización
  offline-first.
- La arquitectura debe permitir añadir menús después sin rediseñar el modelo: los platos
  tendrán identificador UUID global y pertenecerán a un negocio.
- **Propuesta (no aprobada):** `menus(id, negocio_id, nombre, vigencia…)` y
  `menu_platos(id, negocio_id, menu_id, plato_id, orden, precio_en_menu?)`, con clave
  foránea compuesta `(negocio_id, plato_id)` para impedir mezclar negocios.

### 8.3 D3. Duplicados durante la migración (aprobado)

- **Prohibido** renombrar, fusionar o eliminar automáticamente insumos o platos
  duplicados.
- Antes de migrar se genera un informe de posibles duplicados:
  - Comparación por nombre normalizado (mayúsculas, espacios, signos equivalentes). El
    nombre guardado no se altera.
  - Por cada registro: identificador, datos que lo distinguen (precio, unidad, merma,
    foto, fecha) y recetas que lo usan.
  - Impacto sobre costos y márgenes de cada opción.
- Dos registros con el mismo nombre **no** se consideran el mismo producto por defecto.
- Cada caso exige una decisión explícita del usuario.
- Las resoluciones quedan vinculadas a la versión exacta (SHA-256) de los datos de
  origen; si el origen cambia, se invalidan y deben revisarse de nuevo.
- Los datos originales permanecen intactos hasta completar y verificar la migración.
- **Propuesta:** clasificar coincidencias en "exactas" (tras normalizar) y "probables"
  (tildes, singular/plural); las probables solo se informan.

### 8.4 D4. Catálogo de unidades (aprobado)

- Catálogo controlado y ampliable.
- Conversión automática **solo** entre unidades compatibles de la misma dimensión
  (por ejemplo 1 kg = 1.000 g; 1 l = 1.000 ml).
- Nunca convertir masa en volumen sin información adicional validada (densidad).
- Las unidades personalizadas no reciben conversiones inventadas.
- No cambiar la unidad de un insumo existente sin analizar las recetas relacionadas y el
  impacto en los costos.
- **No reinterpretar automáticamente** valores antiguos como `10kg`, `10 kg`, `12`, `kg`,
  `un`, `lt` o `porción`.

**Propuesta (no aprobada) de estructura:** `unidades(id, codigo, nombre, dimension,
factor_a_base, activa, negocio_id?)`, con un identificador estable, código normalizado,
nombre visible, dimensión física, factor de conversión (vacío en las personalizadas) y
estado activo/inactivo.

**Catálogo inicial propuesto (no definitivo):**

| Dimensión | Base | Unidades y factor |
|---|---|---|
| Masa | g | kg = 1000 · g = 1 · mg = 0,001 |
| Volumen | ml | l = 1000 · ml = 1 |
| Conteo | unidad | unidad = 1 · docena = 12 |
| Personalizada | — | sin conversión (por ejemplo `porción`, ya usada en plantillas) |

### 8.5 D5. Separar unidad de medida, presentación y precio (aprobado)

Se distinguen:

1. Unidad de medida del insumo (por ejemplo `kg`).
2. Contenido numérico de la presentación de compra (por ejemplo `10`).
3. Unidad del contenido de la presentación (por ejemplo `kg`).
4. Precio de compra de la presentación (por ejemplo `$5.000`).
5. Cantidad y unidad consumidas por cada ingrediente de una receta (por ejemplo `150 g`).

Ejemplo: un envase de 10 kg cuesta $5.000 → $500 por kg → $0,50 por g; si una receta usa
150 g, el costo de ese ingrediente es $75 (antes de merma).

- El costo por unidad se deriva del precio y del contenido **solo** si ambos son válidos
  y las unidades son compatibles.
- La fórmula actual `costo_real_plato` (`services/calculo_costos.py`) **no se modifica**
  hasta disponer de una comparación verificable entre los resultados anteriores y los
  nuevos.
- **Pendiente** (no aprobado): campos definitivos, precisión numérica y tratamiento de
  insumos sin presentación de compra (ver 8.10).
- **Propuesta:** en el insumo, `unidad_id`, `presentacion_contenido`,
  `presentacion_unidad_id` y `presentacion_precio`; en el ingrediente, `cantidad` y
  `unidad_id`. Guardar la cantidad tal como se ingresó y calcular la conversión.

### 8.6 D6. Confirmación de ambigüedades en la migración (aprobado)

Durante la futura migración de JSON a SQLite y la posterior asignación a un negocio en
Supabase:

1. Inspeccionar las unidades y cantidades originales.
2. Identificar los casos cuya interpretación no sea segura.
3. Mostrar el valor original, las interpretaciones posibles, las recetas afectadas y el
   impacto estimado sobre costos y márgenes.
4. Exigir confirmación explícita del usuario para cada caso ambiguo.
5. No migrar los registros sin resolver como si fueran datos confirmados.
6. Trabajar exclusivamente sobre una copia de los datos; no modificar los JSON originales
   ni los respaldos.
7. Validar relaciones, cantidades, costos y márgenes antes de aceptar la migración.
8. Vincular las resoluciones al SHA-256 exacto del origen; si cambia, exigir una nueva
   validación.
9. La política D3 de duplicados sigue vigente.

### 8.7 D7. Funcionamiento sin conexión y sincronización posterior (aprobado)

**Nada de esto está implementado.** Hoy la app guarda sus datos en JSON locales
(sección 3.1); no tiene SQLite, cola de sincronización ni conexión con Supabase. D7 fija
el comportamiento que deberá tener la arquitectura futura.

**Operaciones disponibles sin conexión (aprobado)**

Sin internet, SmartCost debe permitir sobre los datos del negocio:

- Crear, consultar, editar y eliminar ingredientes (insumos).
- Crear, consultar, editar y eliminar platos.
- Gestionar las relaciones entre ingredientes y recetas.
- Registrar y actualizar los precios de compra propios del negocio.
- Calcular los costos de las recetas con los datos locales disponibles.

Condiciones:

- Las eliminaciones respetan las políticas ya acordadas en D1–D6 (roles, dependencias,
  revisión de recetas y borrado lógico). D7 no introduce excepciones. La política para
  insumos usados en recetas sigue pendiente (8.10) y D7 no la resuelve.
- Cada operación está sujeta al rol del usuario en ese negocio (D1); por ejemplo, un
  `lector` tampoco puede editar sin conexión (derivado de D1). Sin conexión se aplica el
  rol conocido localmente (D7.1); el mecanismo para actualizarlo o invalidarlo queda
  pendiente (8.10).

**D7.1. Apertura y uso sin conexión (aprobado, 2026-10-29)**

- Un usuario que ya inició sesión en el dispositivo puede volver a abrir SmartCost sin
  internet y trabajar con los datos locales disponibles.
- El acceso sin conexión se basa en una **sesión establecida previamente** en ese
  dispositivo y en los **datos locales**. El primer inicio de sesión en un dispositivo
  requiere conexión: no se promete acceso offline sin una sesión previa.
- Se distinguen dos cosas:
  - **Abrir la app:** permitido con una sesión previa, aunque no haya conexión.
  - **Operar:** cada operación local se permite según el rol del usuario **conocido
    localmente** en ese negocio (D1).
- Los permisos del servidor siguen siendo la autoridad para las operaciones remotas: lo
  permitido localmente puede ser rechazado al sincronizar.
- Requisito futuro: si la sesión caduca o el servidor rechaza una operación, las
  operaciones pendientes se conservan; el rechazo se muestra al usuario y se resuelve sin
  perder silenciosamente los datos locales.
- Pendientes de seguridad (8.10): tiempo de validez del acceso sin conexión, mecanismo de
  revocación de sesiones y de roles, y actualización del rol conocido localmente.

**SQLite como base local (aprobado)**

- SQLite será la base operativa local de la arquitectura futura.
- Requisito futuro: los cambios se conservan aunque la app se cierre, el teléfono se
  reinicie o el dispositivo pase un período prolongado sin conexión.
- La migración desde los JSON actuales se diseñará e implementará por separado, bajo D3 y
  D6. No forma parte de D7 y no se ha realizado.

**Cola persistente de sincronización (requisito futuro)**

Los cambios locales se registrarán en una cola persistente que sobreviva al cierre de la
app y al reinicio del dispositivo. La implementación deberá contemplar:

- Identificador único por operación.
- Reintentos ante errores temporales de red.
- Idempotencia: una operación reintentada no se aplica dos veces.
- Estados claros: pendiente, en proceso, sincronizada, con error y con conflicto.
- Registro de errores que permita diagnosticar y reintentar.
- Orden y dependencias entre operaciones relacionadas (por ejemplo, un ingrediente no se
  envía antes que su plato y su insumo).
- Recuperación segura si la app se cierra durante una sincronización.
- Eliminaciones y cambios de permisos tratados sin resucitar registros eliminados ni
  perder operaciones pendientes.

Los detalles técnicos de 8.8 (estados, espera creciente, versiones) son propuestas que
podrían cumplir estos requisitos; no están aprobados.

**Supabase/PostgreSQL como servidor central (requisito futuro)**

Con conexión, SmartCost sincronizará los cambios autorizados y descargará los cambios del
negocio y del usuario autenticados, respetando:

- Aislamiento de los datos por negocio.
- Roles y permisos de D1.
- Autorización validada en el servidor (políticas RLS de Supabase y demás controles).
- Prohibición de incluir claves privilegiadas, como `service_role`, en la app.
- Manejo de sesiones caducadas, permisos revocados y errores de autenticación.
- Una operación no se considera sincronizada hasta recibir confirmación válida del
  servidor.

**Conflictos entre dispositivos (aprobado)**

Si dos dispositivos modifican el mismo registro sin conexión:

- No se sobrescriben datos silenciosamente.
- Se detecta que la versión local y la remota divergieron.
- Se conserva información suficiente para explicar el conflicto.
- Un usuario autorizado lo resuelve de forma explícita.
- Las modificaciones pendientes no se pierden durante el proceso.

**D7.2. Resolución manual de conflictos (aprobado, 2026-10-29)**

Cuando dos dispositivos modifican el mismo registro y las versiones divergen:

- SmartCost detecta el conflicto y muestra los valores relevantes de la versión local y
  de la versión del servidor.
- Un usuario autorizado elige explícitamente qué versión conservar.
- No se sobrescriben cambios silenciosamente.
- La resolución registra qué versión se eligió, y la decisión se sincroniza de forma
  consistente.
- Si el registro vuelve a cambiar mientras se resuelve el conflicto, se detecta y se
  solicita una nueva revisión.

Todo lo anterior es requisito futuro: no existe en el código.

Propuesta (no aprobada): combinar automáticamente los cambios en campos diferentes solo
cuando se pueda demostrar que no hay incompatibilidades; los cambios concurrentes sobre el
mismo campo siempre se revisan. D7.2 no aprueba esta combinación automática. Pendiente:
qué campos nunca se combinan automáticamente, qué roles resuelven cada tipo de conflicto
y cómo se registra la resolución (8.10).

**Precios propios de cada negocio (aprobado)**

- Cada propietario, administrador o editor autorizado puede registrar y actualizar los
  precios de compra de su negocio (D1.1), solo dentro de los negocios en los que tiene
  ese rol.
- Los precios de referencia del mercado chileno, si se incorporan más adelante, serán
  opcionales y estarán separados de los precios propios: no sustituyen automáticamente los
  precios de compra del negocio ni se comparten entre negocios sin autorización.

**Estado de sincronización en la interfaz (requisito futuro)**

La interfaz futura deberá informar claramente:

- Si el dispositivo está sin conexión.
- Cuántos cambios están pendientes.
- Si hay una sincronización en curso.
- Cuándo se completó la última sincronización satisfactoria.
- Si hay errores o conflictos que requieren atención.

No se han diseñado pantallas ni controles.

### 8.8 Otras líneas de diseño (propuestas, no aprobadas)

Presentadas en la fase de diseño; sirven de referencia, pero ninguna está aprobada para
implementarse. D7 (8.7) convirtió en requisito la cola persistente y la detección de
conflictos, pero no los detalles técnicos de esta lista:

- Identificadores UUID generados en el cliente; los IDs enteros actuales se convierten
  mediante un mapa de equivalencias persistente.
- Columnas de sincronización fijadas por el servidor: `version`, `sync_seq`,
  `created_at`, `updated_at`, `deleted_at` (borrado lógico), `created_by`, `updated_by`,
  `ultima_op`.
- Claves foráneas compuestas `(negocio_id, id)` para que una receta no pueda apuntar a
  datos de otro negocio.
- Índices únicos parciales por nombre normalizado dentro de cada negocio.
- Cola local con operaciones idempotentes, reintentos con espera creciente, detección de
  conflictos por versión y fusión automática solo cuando cambiaron campos distintos.
- Conexión REST con la biblioteca estándar (`urllib`) en lugar de `supabase-py`, cuya
  dependencia `pydantic-core` (Rust) probablemente no compila con python-for-android.

### 8.9 Riesgo prioritario: unidad de medida y presentación mezcladas

El campo `unidad` actual es texto libre y **mezcla unidad de medida y presentación de
compra**. En los datos de ejemplo y en las plantillas aparecen valores como `10kg`,
`10 kg`, `5kg`, `12`, `kg`, `un`, `lt` y `porción`: algunos parecen describir un envase
(`10kg`) y otros una unidad de medida (`kg`).

El cálculo actual es `cantidad × precio × (1 + merma)`. Si `precio` corresponde al envase
y `cantidad` a una fracción de la unidad (o al revés), el costo resultante puede ser
incorrecto: se podría estar usando el precio del envase como si fuera un precio
unitario.

- **No se afirma** que todos los registros tengan este problema: algunos pueden estar
  bien interpretados por el usuario.
- **No se han cambiado** datos ni fórmulas.
- Requiere un diagnóstico de solo lectura y la confirmación del usuario caso por caso
  (D6) antes de cualquier conversión.

### 8.10 Pendientes técnicos (sin decisión)

**Unidades y costos**

- Campos definitivos; si el precio unitario se almacena o se calcula siempre.
- Tratamiento de insumos sin presentación de compra (precio directo por unidad).
- ~~Precisión numérica~~ **Decidido el 2026-11-26 (8.14):** `NUMERIC` en PostgreSQL,
  decimales como texto en SQLite y cálculo con `Decimal`. Sigue pendiente la tolerancia
  aceptada al comparar los resultados `float` actuales con los `Decimal`.
- Catálogo definitivo (`porción`, `cc`, `taza`…), unidades personalizadas por negocio o
  globales, y reglas de conversión.
- Interpretaciones que se ofrecerán para cada valor ambiguo y tratamiento de los
  registros sin resolver (excluir e informar, o bloquear la migración).
- Ubicación y formato del informe de resoluciones, **fuera de Git** si contiene datos
  reales.

**Permisos y cuentas**

- Celdas ⏳ de la matriz de 8.1 y forma de administrar los roles.
- Procedimientos de transferencia de propiedad y de archivo o eliminación del negocio.
- Autenticación online/offline (propuesta: correo y contraseña con código OTP; verificador
  local para entrar sin conexión) y almacenamiento seguro de credenciales y tokens.
- Vinculación de las cuentas locales existentes con Supabase Auth.

**Infraestructura**

- Proyectos Supabase de desarrollo y producción, y dónde guardar su URL y clave pública
  sin subirlas a Git. La clave `service_role` nunca va en la app.
- Compatibilidad Android: receta `sqlite3` en `buildozer.spec`, permisos `INTERNET` y
  `ACCESS_NETWORK_STATE` (hoy no declarados) y, solo si fuera necesario, `certifi`.
- Tamaño máximo de las fotos y si se borran al borrar el plato.
- Plazo de retención antes de la eliminación definitiva de registros borrados.
- Política de borrado de insumos utilizados en recetas (cascada lógica o bloqueo).
- Quién resuelve los conflictos de sincronización.
- Arquitectura futura de menús (8.2).

**Sin conexión y sincronización (D7)**

- Política de combinación automática de campos distintos (propuesta no aprobada; D7.2) y
  lista de campos que nunca se combinan sin revisión.
- Qué roles pueden resolver cada tipo de conflicto (D7.2 exige un usuario autorizado; la
  celda del `editor` sigue ⏳ en 8.1).
- Cómo se registra la resolución de un conflicto (historial o auditoría, visibilidad) y
  si se permite combinar manualmente valores de ambas versiones o solo elegir una.
- Cómo se presentan y resuelven las operaciones hechas sin conexión que el servidor
  rechace (D7.1 exige conservarlas y mostrar el rechazo; falta definir el flujo).
- Momentos de sincronización (al abrir, tras cada cambio, periódica, en segundo plano) y
  límites de tamaño de la cola.
- Si las fotos forman parte de la cola de sincronización y cuándo se suben.
- Si se conserva el historial de precios de compra o solo el valor vigente.
- Fuente, frecuencia de actualización y condiciones de uso de los precios de referencia
  del mercado chileno, si se incorporan.

**Seguridad del acceso sin conexión (D7.1)**

- Tiempo de validez del acceso sin conexión (no definido; no se debe inventar).
- Mecanismo definitivo de revocación de sesiones y de roles, y cómo se aplica a un
  dispositivo que sigue sin conexión.
- Cómo y cuándo se actualiza o invalida el rol conocido localmente.
- Protección de la sesión y de los datos locales en el dispositivo (relacionado con el
  almacenamiento seguro de credenciales y tokens de "Permisos y cuentas").

### 8.11 Riesgos conocidos

- **Seguridad:** error en RLS o triggers que permita escalar privilegios o ver datos de
  otro negocio (incluido Storage); exposición de la clave `service_role`; tokens
  guardados sin protección adicional en el teléfono; acceso sin conexión con una sesión
  previa en un dispositivo perdido o con permisos ya revocados, mientras la revocación no
  pueda aplicarse sin conexión (D7.1).
- **Integridad:** interpretación errónea de unidades (8.9); diferencias de redondeo al
  pasar de `float` a `Decimal`; duplicados creados por CSV o plantillas justo antes de
  migrar; importaciones actuales no atómicas (recetas a medias); fotos huérfanas y rutas
  antiguas en el campo `imagen`.
- **Sincronización:** cambio de unidad de un insumo mientras otro dispositivo está sin
  conexión; cambios de rol o expulsiones con operaciones pendientes (rechazos que no
  deben perderse en silencio); operaciones encoladas antes de una actualización que
  cambie el esquema; períodos prolongados sin conexión (sesión caducada, gran divergencia
  entre dispositivos, cola de gran tamaño).

### 8.12 Propuesta de protección reforzada de datos locales

**Estado: propuesta de arquitectura pendiente de validación técnica; implementación no
autorizada.** Nada de esta subsección está aprobado como decisión ni implementado. Hoy los
datos se guardan sin cifrado propio de la app en la carpeta privada de Android (3.1).
No modifica D1–D7.

**Requisitos propuestos**

1. **Cifrado en reposo** de la base de datos local y de los datos sensibles.
2. **Protección de las claves de cifrado** con mecanismos apropiados de Android. Evaluar
   Android Keystore y sus limitaciones de integración con Python (acceso mediante
   pyjnius, claves no exportables, comportamiento según la versión de Android).
3. **SQLite cifrado compatible** con Python, Kivy, Buildozer, Android API 24+ y ARM64
   (`arm64-v8a`). **No se asume** que SQLCipher u otra biblioteca funcione con
   python-for-android hasta verificarlo con una compilación de prueba.
4. **Protección del resto de archivos:** fotografías, archivos auxiliares de SQLite (WAL,
   `-shm`, diarios y temporales), exportaciones (CSV u otras) y respaldos.
5. **Autenticación para reanudar el acceso** cuando corresponda, coherente con la política
   de acceso sin conexión de D7.1. El tiempo de validez de ese acceso **sigue sin
   aprobarse** (8.10); 30 días es solo un valor propuesto, pendiente de aprobación.
6. **Conservación de los cambios pendientes** de sincronización al bloquear o revalidar
   la sesión: bloquear no descarta la cola ni los datos locales (coherente con D7.1).
7. **Plan de migración de los datos existentes** con respaldo verificable, validación de
   integridad y recuperación ante fallos (ver "Migración" más abajo).
8. **Análisis** de rendimiento, recuperación de claves, reinstalación, pérdida del
   dispositivo e incompatibilidades.
9. **Prohibido** almacenar claves secretas en el código fuente, en el APK o junto a los
   datos cifrados sin una protección adecuada.

**Implicaciones**

- **Cifrar SQLite no basta por sí solo.** No protege automáticamente:
  - las fotos, que hoy son archivos sueltos en `<datos>/imagenes/` y que Kivy carga desde
    una ruta de archivo;
  - los archivos auxiliares, si la solución elegida no los cifra (hay que verificarlo);
  - las exportaciones que la app escriba fuera de la base;
  - los respaldos.
- **Respaldos:** el procedimiento actual (6.3) copia `files/` con `run-as`. Con cifrado,
  esa copia contendría datos cifrados y solo serviría si la clave sigue disponible; el
  procedimiento de respaldo y restauración tendría que rediseñarse.
- **Recuperación:** si se pierde la clave (reinstalación, restablecimiento de fábrica,
  invalidación de la clave en Keystore), los datos locales cifrados serían
  irrecuperables. Lo ya sincronizado podría recuperarse del servidor; **los cambios
  pendientes no**.
- **JSON originales:** migrar a una base cifrada no elimina los JSON en texto plano. En
  memoria flash no se puede garantizar un borrado seguro, y borrar los originales
  requiere una aprobación expresa aparte (siguen vigentes las reglas de la sección 2 y
  de D6).
- **Modelo de amenazas por definir:** Android ya aísla la carpeta privada de la app y, en
  muchos dispositivos, cifra el almacenamiento. Hay que precisar frente a qué protege el
  cifrado adicional (dispositivo con root, extracción física, copias de seguridad,
  versiones debug) para elegir la solución proporcional.

**Migración (propuesta)**

1. Respaldo nuevo y verificado con SHA-256 antes de empezar (6.3); no se tocan los
   respaldos existentes.
2. Migración sobre una copia de trabajo, nunca sobre los originales.
3. Validación antes de aceptar: integridad de la base, recuentos, relaciones, costos y
   márgenes (mismo criterio de comparación que D6).
4. Si algo falla, se descarta la copia y la app sigue con el almacenamiento anterior.
5. Los originales se conservan hasta completar y verificar la migración.

**Pruebas técnicas necesarias antes de elegir una solución**

- Compilar un APK de prueba con cada biblioteca candidata (por ejemplo SQLCipher u
  opciones similares; ninguna está elegida) y ejecutarlo en Android 7.0 (API 24) y en una
  versión reciente, en ARM64.
- Crear, abrir, escribir y consultar una base cifrada desde Python; comprobar que no se
  puede abrir sin la clave o con una clave incorrecta.
- Inspeccionar los archivos en disco (base, WAL, `-shm`, temporales) y verificar que no
  contienen texto plano.
- Guardar y recuperar la clave con Android Keystore mediante pyjnius; probar qué ocurre
  tras actualizar la app (`adb install -r`), reinstalarla, cambiar el bloqueo de pantalla
  o la biometría y restablecer el dispositivo.
- Medir el impacto en el tiempo de arranque, en las consultas y en las escrituras con la
  cola de sincronización, y en el tamaño del APK.
- Interrumpir la app durante la migración y comprobar la recuperación.
- Revisar las licencias de las bibliotecas candidatas.

**Preguntas técnicas abiertas**

- Modelo de amenazas y nivel de protección requerido.
- Biblioteca de SQLite cifrado y forma de integrarla en python-for-android (receta
  existente, receta propia u otra vía).
- Esquema de claves: clave directa en Keystore o clave de datos envuelta por una clave de
  Keystore; si la clave se vincula a la autenticación del usuario.
- Cifrado de fotos y cómo mostrarlas en Kivy sin dejar copias descifradas en disco.
- Cuándo se pide reautenticación (al abrir, tras inactividad, al vencer la validez
  offline) y con qué método (contraseña, PIN, biometría; esta última ya figura como
  pendiente en 4.2).
- Si la sincronización puede ejecutarse mientras la app está bloqueada.
- Formato y cifrado de los respaldos y de las exportaciones, y política de copia de
  seguridad automática de Android.
- Qué hacer con los JSON en texto plano después de una migración verificada.
- Comportamiento ante pérdida del dispositivo (relacionado con la revocación pendiente
  en 8.10).

### 8.13 Propuesta de recuperación segura de datos locales cifrados

**Estado: propuesta pendiente de validación técnica y de aprobación final;
implementación no autorizada.** Complementa la propuesta 8.12 sin modificarla. No
modifica D1–D7 ni 8.10. Ningún mecanismo descrito aquí está implementado ni probado, y no
se afirma que funcione hasta disponer de pruebas verificables.

**Separación de claves (a evaluar)**

Tres elementos distintos, que no deben confundirse ni guardarse juntos sin protección:

| Elemento | Qué es | Dónde viviría (propuesta) |
|---|---|---|
| Clave de datos | Clave aleatoria que cifra la base local (y, si se decide, fotos y copias) | Nunca en claro fuera de la memoria de la app |
| Clave del dispositivo | Clave protegida por Android Keystore que envuelve la clave de datos | Keystore del dispositivo; no exportable |
| Secreto de recuperación | Secreto controlado por el usuario que permite recuperar la clave de datos | Solo en poder del usuario |

- Evaluar una **clave de datos aleatoria** con **dos envolturas criptográficas
  independientes**: una con la clave del dispositivo (uso diario) y otra derivada del
  secreto de recuperación (recuperación). Perder una envoltura no debe comprometer la otra.
- Opción a evaluar, **no aprobada** (ni ella ni su formato): un **código de recuperación
  aleatorio de alta entropía**, generado localmente y mostrado una sola vez al usuario.

**Papel del servidor**

- El servidor **puede** almacenar material de recuperación cifrado (por ejemplo, la
  clave de datos envuelta con el secreto de recuperación).
- El servidor **nunca** almacena la clave de datos ni el secreto de recuperación en texto
  plano.
- Recuperar la **cuenta** (Supabase Auth) **no** implica recuperar automáticamente la
  clave ni los datos cifrados: sin el secreto de recuperación, el material cifrado del
  servidor no sirve.

**Recuperación en otro dispositivo (a evaluar)**

1. Autenticación de la cuenta en el nuevo dispositivo.
2. Validación de permisos en el servidor (roles de D1 y RLS).
3. Descarga del material de recuperación cifrado.
4. Recuperación local de la clave de datos con el secreto que introduce el usuario; el
   secreto no se envía al servidor.
5. Nueva envoltura de la clave de datos con la Keystore del nuevo dispositivo.

**Qué se puede recuperar**

| Tipo de dato | Recuperación |
|---|---|
| Datos ya sincronizados con Supabase | Desde el servidor, con autenticación y permisos (D1). Según el diseño propuesto no dependen del secreto de recuperación local. A confirmar. |
| Copias cifradas remotas (si se crean) | Solo con el secreto de recuperación y si la copia está íntegra; tan actualizadas como la última copia. |
| Cambios que nunca salieron del dispositivo | **No recuperables** tras perder el dispositivo, salvo que exista otra copia remota cifrada, íntegra y suficientemente actualizada. |

**Amenazas y escenarios a evaluar**

- **Intentos de adivinar el código:** si el material cifrado se descarga, un atacante
  puede probar códigos sin conexión y los límites del servidor no lo frenan; la
  protección depende de la entropía del código y de la función de derivación. Evaluar
  también límites de descarga en el servidor.
- **Pérdida del código:** sin el código, los datos que solo estén en la copia cifrada son
  irrecuperables. Definir cómo se avisa al usuario y si se permite generar un código
  nuevo mientras el dispositivo original siga disponible.
- **Rotación de claves:** regenerar el código implica volver a envolver la clave de
  datos; cambiar la clave de datos implica volver a cifrar la base y las copias.
- **Revocación de acceso:** qué ocurre con el material de recuperación de un miembro
  expulsado o de un dispositivo revocado (relacionado con la revocación pendiente en
  8.10).
- **Dispositivo comprometido mientras está desbloqueado:** el atacante podría leer los
  datos con la clave en uso; la recuperación no lo evita. Evaluar revocación y rotación
  posteriores.

**Prohibiciones**

- El código de recuperación nunca se guarda en logs, telemetría, analítica, código
  fuente ni almacenamiento remoto en texto plano.
- No se guardan claves secretas en el código, en el APK ni junto a los datos cifrados sin
  protección adecuada (igual que el requisito 9 de 8.12).

**Relación con el acceso sin conexión**

La política de acceso sin conexión sigue **pendiente de aprobación** (D7.1 y 8.10, sin
cambios). Esta propuesta no fija ningún tiempo de validez.

**Preguntas técnicas abiertas**

- Formato y entropía del código de recuperación (longitud, alfabeto, legibilidad, si se
  divide en grupos).
- Algoritmo de envoltura de claves y función de derivación del código, y su
  disponibilidad en python-for-android.
- Protección contra intentos de adivinar el código, en el dispositivo y en el servidor.
- Si existirán copias remotas cifradas, con qué frecuencia y cómo se verifica su
  integridad.
- Si el material de recuperación es por usuario, por dispositivo o por negocio.
- Recuperación ante pérdida o invalidación de la clave de Keystore (reinstalación,
  cambio de bloqueo de pantalla o biometría, restablecimiento).
- Compatibilidad de Android Keystore con API 24+ y ARM64 y su acceso desde Python
  (pyjnius).

**Pruebas aisladas necesarias antes de migrar datos reales**

Solo con datos sintéticos, en un dispositivo o emulador de pruebas y en un proyecto
Supabase de desarrollo; nunca con datos ni respaldos reales.

- Generar la clave y las dos envolturas; abrir la base con la clave del dispositivo.
- Simular la pérdida del dispositivo (borrar los datos de la app o usar otro emulador) y
  recuperar en un segundo dispositivo con el código correcto.
- Comprobar que un código incorrecto no abre los datos y medir el costo de cada intento.
- Comprobar que, sin el código, la cuenta recuperada no da acceso a los datos cifrados.
- Verificar que el servidor no recibe en ningún momento la clave de datos ni el código
  (inspección de peticiones y de la base remota).
- Buscar el código en logs del dispositivo (`logcat`) y del servidor para confirmar que
  no aparece.
- Probar la invalidación de la clave de Keystore, la reinstalación y la rotación del
  código.
- Confirmar que los cambios no sincronizados se pierden en los escenarios previstos y que
  la app lo comunica claramente.

### 8.14 Inventario y costos de reposición (aprobado, 2026-11-26)

**Problema que resuelve.** Un insumo comprado por volumen (por ejemplo un saco de 25 kg)
se consume en parte y sube de precio antes de agotarse. Con un solo precio por insumo, la
cotización queda desfasada o la valoración del inventario se distorsiona.

**Decisiones del autor**

- Cantidades en una **unidad base** por insumo: `g`, `ml` o `unidad` (catálogo de D4;
  conversión solo dentro de la misma dimensión).
- Dinero y cantidades con tipo exacto: `NUMERIC` en PostgreSQL, en **todo** el esquema
  (resuelve el pendiente de precisión de 8.10).
- Cada insumo mantiene `stock_actual`, `costo_promedio` (costo promedio ponderado: valoración
  contable), `costo_reposicion` (último costo unitario: para cotizar sin perder margen) y la
  fecha de ese costo.
- Historial de compras con `cantidad_comprada` (en unidad base), `costo_total` y
  `costo_unitario` como columna generada. Un trigger `AFTER INSERT` bloquea el insumo con
  `SELECT … FOR UPDATE`, suma el stock, recalcula el promedio y actualiza la reposición.
- **Cotizaciones y recetas** usan `costo_reposicion`. **Consumos y producción** descuentan
  el stock y registran el costo contable con `costo_promedio`.
- **Actualización manual de mercado:** cambia solo el costo de reposición y su fecha, sin
  compra física.
- **Alerta de desfase** cuando el costo tiene más de 30 días.
- **Merma:** se guarda como **fracción**, igual que hoy (0,1 = 10 %). La pantalla la pide
  y la muestra en porcentaje. El servidor exige 0 ≤ merma < 1.
- **Stock negativo:** se permite y se marca con un aviso.

**Propuestas aprobadas el mismo día**

1. D5 sigue vigente: `costo_real_plato()` no cambia. El costo proyectado es una función
   nueva, y un informe compara ambos resultados por plato. Las pantallas se cambian solo
   cuando se apruebe esa comparación.
2. Los insumos actuales quedan **sin unidad base ni stock** hasta confirmar su unidad caso
   por caso (D4/D6). Mientras tanto siguen funcionando con el `precio` de hoy.
3. Sin conexión (D7) el **servidor es la autoridad**: aplica compras y consumos en el orden
   en que llegan, y el teléfono muestra valores **provisionales** hasta sincronizar.
4. Registran compras, consumos, producciones y precios de mercado: `propietario`,
   `administrador` y `editor` (amplía D1.1). El `lector` solo consulta.

**Criterios de implementación** (PR #6; derivados de lo anterior y revisables)

- El costo de reposición solo se reemplaza si el dato nuevo no es más antiguo que el
  vigente, para que una compra registrada tarde sin conexión no pise un precio más nuevo.
  El promedio sí la incorpora.
- Si el stock previo es 0 o negativo, el promedio pasa a ser el costo de la compra.
- Las compras y los consumos no suben la `version` del insumo, para no provocar conflictos
  falsos con ediciones de otro dispositivo. Sí suben `sync_seq`.
- Stock y costos los calcula solo el servidor: el cliente no puede escribirlos.
- La unidad base no se cambia una vez fijada (D4). Compras y consumos son inmutables:
  corregirlos queda pendiente.
- Producción: `cantidad × factor de la unidad × porciones × (1 + merma)`. Exige que cada
  ingrediente tenga unidad compatible con la unidad base de su insumo.

**Estado**

- Escrito y probado en el PR #6: 84 pruebas pgTAP en un Postgres desechable (incluidas la
  concurrencia y la reversión) y 46 pruebas de Python.
- No aplicado en Supabase, no conectado a las pantallas y sin migrar datos reales.

**Pendientes**

- Confirmar la unidad base de cada insumo actual (D6): dónde se guardan las confirmaciones
  sin modificar los JSON originales.
- Flujo para corregir o anular una compra o un consumo.
- Si se conserva el historial de precios de mercado (relacionado con 8.10).
- Tolerancia al comparar los costos `float` actuales con los `Decimal`.
