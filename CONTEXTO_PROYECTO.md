# Contexto del proyecto SmartCost

Documento de referencia para retomar el desarrollo (personas o asistentes de IA).
Describe reglas, arquitectura y estado **verificado** del proyecto. Lo que no se pudo
comprobar está marcado como **pendiente de confirmar**.

Última revisión: 2026-10-29, sobre la rama `avance/smartcost-octubre-2026` (commit `432999d`).

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

Convención usada en esta sección:

- **Aprobado:** decisión explícita del autor del proyecto.
- **Requisito futuro:** obligación aprobada que deberá cumplir la implementación; todavía
  no existe en el código.
- **Propuesta:** recomendación técnica aún no aprobada.
- **Pendiente:** cuestión abierta sin decisión.

Las decisiones D1–D7 fueron aprobadas el 2026-10-29.

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
  - `editor`: crea y modifica insumos, platos y recetas; no administra miembros; sus
    eliminaciones respetan las reglas de integridad y recuperación.
  - `lector`: solo consulta la información autorizada.
- Protecciones obligatorias:
  - Todo negocio conserva **al menos un propietario**.
  - Nadie puede asignarse ni asignar el rol `propietario` fuera del procedimiento de
    transferencia (protección contra escalada de privilegios).
  - El rol `lector` no tiene ninguna política de escritura.

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
  `lector` tampoco puede editar sin conexión (derivado de D1). Cómo se conoce y se
  actualiza el rol mientras no hay conexión queda pendiente (8.10).

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

Propuesta (no aprobada): combinar automáticamente los cambios en campos diferentes solo
cuando se pueda demostrar que no hay incompatibilidades; los cambios concurrentes sobre el
mismo campo siempre se revisan. Pendiente: qué campos nunca se combinan automáticamente y
quién resuelve cada tipo de conflicto (8.10).

**Precios propios de cada negocio (aprobado)**

- Cada propietario o administrador autorizado puede registrar y actualizar los precios de
  compra de su negocio.
- Los precios de referencia del mercado chileno, si se incorporan más adelante, serán
  opcionales y estarán separados de los precios propios: no sustituyen automáticamente los
  precios de compra del negocio ni se comparten entre negocios sin autorización.
- Pendiente de aclarar: la matriz de D1 permite al `editor` modificar insumos; falta
  decidir si eso incluye sus precios de compra (8.10). D1 no se ha modificado.

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
- Precisión numérica (propuesta: `numeric(18,6)` en PostgreSQL, decimales como texto en
  SQLite y cálculo con `Decimal`) y tolerancia aceptada al comparar `float` con `Decimal`.
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

- Política de combinación automática de campos distintos y lista de campos que nunca se
  combinan sin revisión.
- Cómo se conocen y aplican los roles sin conexión, y qué ocurre con las operaciones
  hechas offline que el servidor rechace por un permiso revocado.
- Si el primer uso en un dispositivo exige conexión (inicio de sesión inicial y descarga
  de datos).
- Tiempo máximo sin conexión admitido y comportamiento cuando la sesión caduca durante ese
  período.
- Momentos de sincronización (al abrir, tras cada cambio, periódica, en segundo plano) y
  límites de tamaño de la cola.
- Si las fotos forman parte de la cola de sincronización y cuándo se suben.
- Si el `editor` puede modificar los precios de compra (D1 frente a D7).
- Si se conserva el historial de precios de compra o solo el valor vigente.
- Fuente, frecuencia de actualización y condiciones de uso de los precios de referencia
  del mercado chileno, si se incorporan.

### 8.11 Riesgos conocidos

- **Seguridad:** error en RLS o triggers que permita escalar privilegios o ver datos de
  otro negocio (incluido Storage); exposición de la clave `service_role`; tokens
  guardados sin protección adicional en el teléfono.
- **Integridad:** interpretación errónea de unidades (8.9); diferencias de redondeo al
  pasar de `float` a `Decimal`; duplicados creados por CSV o plantillas justo antes de
  migrar; importaciones actuales no atómicas (recetas a medias); fotos huérfanas y rutas
  antiguas en el campo `imagen`.
- **Sincronización:** cambio de unidad de un insumo mientras otro dispositivo está sin
  conexión; cambios de rol o expulsiones con operaciones pendientes (rechazos que no
  deben perderse en silencio); operaciones encoladas antes de una actualización que
  cambie el esquema; períodos prolongados sin conexión (sesión caducada, gran divergencia
  entre dispositivos, cola de gran tamaño).
