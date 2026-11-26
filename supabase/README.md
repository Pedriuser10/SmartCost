# Supabase / PostgreSQL de SmartCost

Esquema del servidor central de la arquitectura offline-first (CONTEXTO_PROYECTO.md,
sección 8). **Todavía no está aplicado en ningún proyecto Supabase** y la app aún no se
conecta a él.

| Archivo | Qué es |
|---|---|
| `migrations/20261126000000_esquema_inicial.sql` | Migración (UP): tablas, restricciones, funciones, triggers, RLS |
| `rollback/20261126000000_esquema_inicial.down.sql` | Reversión (DOWN). **Borra todo**: solo en desarrollo |
| `tests/database/*.test.sql` | Pruebas pgTAP (83) |
| `probar_en_contenedor.sh` | Aplica UP, pruebas, DOWN y UP otra vez en un Postgres desechable |

## Probar

```bash
bash supabase/probar_en_contenedor.sh
```

Usa Docker con la imagen `public.ecr.aws/supabase/postgres` y un contenedor temporal, sin
puertos ni volúmenes con nombre. No toca ningún proyecto Supabase, ni local ni remoto. Con
un proyecto local de la CLI (`supabase start`) también sirve `supabase test db`.

## Aplicar en un proyecto Supabase

Solo con autorización explícita del propietario del proyecto:
`supabase link --project-ref <ref>` y luego `supabase db push`. La clave `service_role`
nunca va en la app ni en este repositorio.

## Inventario y costos

Todas las cantidades van en la unidad base del insumo (`g`, `ml` o `unidad`). Dinero y
cantidades se guardan como `numeric`.

| Columna (`insumos`) | Para qué | Quién la cambia |
|---|---|---|
| `stock_actual` | Existencias (puede quedar negativo: aviso) | Compras, consumos, producción |
| `costo_promedio` | Costo promedio ponderado: valoración contable | Cada compra |
| `costo_reposicion` | Último costo conocido: para cotizar | Compras y `actualizar_costo_reposicion()` |
| `costo_actualizado_en` | Fecha de ese costo; más de 30 días ⇒ alerta | Ídem |

- **Compra** (`insert` en `compras_insumos`): un trigger `AFTER INSERT` bloquea el insumo
  con `SELECT … FOR UPDATE`, suma el stock y recalcula el promedio:
  `(stock × promedio + costo_total) / (stock + cantidad)`. Si el stock era 0 o negativo,
  el promedio pasa a ser el costo de la compra. El costo de reposición se reemplaza solo
  si la compra no es más antigua que el costo vigente: así una compra registrada tarde
  (sin conexión) no pisa un precio más nuevo.
- **Consumo** (`insert` en `consumos_insumos`): descuenta el stock y guarda el costo contable
  al promedio vigente. Si el stock queda negativo, se registra y `stock_negativo = true`.
- **Producción** (`registrar_produccion(id, plato, porciones)`): consume cada ingrediente.
  La cantidad es `cantidad × factor de la unidad × porciones × (1 + merma_pct / 100)`.
  La operación es idempotente por `id`.
- **Alza del proveedor sin compra** (`actualizar_costo_reposicion(insumo, costo)`): cambia
  solo el costo de reposición y su fecha.
- **Cotizador**: la vista `insumos_costos` trae `costo_desactualizado` (más de 30 días),
  `sin_costo_reposicion` y `stock_negativo`. El costo proyectado de un plato se calcula en
  la app (`services/calculo_costos.costo_proyectado_plato`, con `Decimal`).
- Una compra o un consumo **no sube la `version`** del insumo. Así no provoca conflictos
  falsos con ediciones hechas en otro dispositivo. `sync_seq` sí sube, para que todos
  reciban el stock nuevo.
- **Concurrencia**: probada a mano con dos compras simultáneas del mismo insumo. La segunda
  esperó al bloqueo y no se perdió ninguna actualización.

### Insumos actuales (D4/D6)

Los insumos que ya existen conservan `unidad` (texto libre) y `precio` tal cual, que usa la
fórmula actual. Entran al inventario solo cuando se confirme su `unidad_base`, caso por
caso. Hasta entonces una compra sobre ellos se rechaza. La `unidad_base` no se cambia una
vez fijada.

## Permisos

Se aplica solo lo aprobado (✅ / ❌ de la matriz de 8.1). **Lo que sigue está denegado
porque está ⏳ o ➜ sin confirmar.** Cada punto se habilita con una migración nueva cuando
se decida:

| Operación | Hoy |
|---|---|
| Administrador edita nombre o moneda del negocio | Denegado |
| Archivar o eliminar el negocio; transferir la propiedad | Denegado a todos (falta el procedimiento) |
| Editor y lector ven la lista de miembros | Solo ven su propia fila |
| Administrador crea administradores, cambia roles o quita miembros | Denegado |
| Cualquiera sale del negocio por su cuenta | Denegado |
| Editor elimina insumos o platos | Denegado (sí puede quitar un ingrediente de una receta) |
| Restaurar registros eliminados | Denegado a todos |
| Lector ve costos y márgenes | **Permitido** (RLS filtra filas, no columnas; ver 8.1) |
| Corregir o anular una compra o un consumo | Denegado (son inmutables; falta decidir el flujo) |

Aprobado el 2026-11-26: propietario, administrador y editor registran compras, consumos,
producciones y precios de mercado; el lector solo consulta.

## Pendiente

- Migrar los datos reales: requiere el informe de duplicados y unidades (D3/D6).
- Cliente de sincronización (cola de `models/db.py` → API REST de Supabase).
- Réplica local del inventario en SQLite, con valores provisionales hasta sincronizar.
- Informe que compare, plato por plato, el costo actual y el proyectado (D5).
- Supabase Storage para las fotos.
