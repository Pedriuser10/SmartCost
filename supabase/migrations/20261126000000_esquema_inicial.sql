-- =============================================================================
-- SmartCost: esquema inicial en Supabase/PostgreSQL
--
-- Aplica lo aprobado en CONTEXTO_PROYECTO.md, sección 8:
--   D1   roles por negocio, verificados en el servidor (RLS + triggers)
--   D1.1 el editor registra compras y actualiza precios de compra
--   D2   sin menús en esta fase; platos con UUID y negocio_id
--   D4   catálogo de unidades; conversión solo dentro de la misma dimensión;
--        la unidad antigua (texto libre) se conserva tal cual y no se reinterpreta
--   D5   la fórmula actual no cambia; el costo proyectado es una función nueva
--   D7   columnas de sincronización (version, sync_seq, borrado lógico) y
--        detección de conflictos por versión
--   Inventario (aprobado el 2026-11-26): stock en unidad base, costo promedio
--        ponderado, costo de reposición, alerta de 30 días, stock negativo con
--        aviso, NUMERIC para dinero y cantidades. La merma se guarda como fracción
--        (0,1 = 10 %), igual que hoy en la app: la pantalla la pide en porcentaje.
--
-- Regla de permisos: se aplica solo lo marcado ✅ o ❌ en la matriz de 8.1.
-- Lo marcado ➜ (derivado, sin confirmar) o ⏳ (pendiente) queda DENEGADO hasta
-- que se decida. La lista está en supabase/README.md.
--
-- Reversión: supabase/rollback/20261126000000_esquema_inicial.down.sql
-- Esta migración no contiene datos de usuarios ni claves.
-- =============================================================================

create schema if not exists privado;
revoke all on schema privado from public;
grant usage on schema privado to authenticated;

create type public.rol_negocio as enum ('propietario', 'administrador', 'editor', 'lector');

-- Contador global de cambios: cada escritura recibe un número mayor que el anterior.
-- Los clientes descargan "todo lo que tenga sync_seq mayor que el último que vi".
create sequence public.sync_seq;

-- -----------------------------------------------------------------------------
-- Catálogo de unidades (D4)
-- -----------------------------------------------------------------------------

create table public.unidades (
    codigo       text primary key,
    nombre       text not null,
    dimension    text not null check (dimension in ('masa', 'volumen', 'conteo')),
    unidad_base  text not null references public.unidades (codigo),
    factor       numeric(18, 6) not null check (factor > 0),   -- cuántas unidades base son 1 de esta
    check (codigo <> unidad_base or factor = 1)                  -- una unidad base vale 1
);

insert into public.unidades (codigo, nombre, dimension, unidad_base, factor) values
    ('g',      'gramo',       'masa',    'g',      1),
    ('ml',     'mililitro',   'volumen', 'ml',     1),
    ('unidad', 'unidad',      'conteo',  'unidad', 1),
    ('kg',     'kilogramo',   'masa',    'g',      1000),
    ('mg',     'miligramo',   'masa',    'g',      0.001),
    ('l',      'litro',       'volumen', 'ml',     1000),
    ('docena', 'docena',      'conteo',  'unidad', 12);

-- -----------------------------------------------------------------------------
-- Tablas
-- -----------------------------------------------------------------------------

create table public.negocios (
    id          uuid primary key default gen_random_uuid(),
    nombre      text not null check (btrim(nombre) <> ''),
    moneda      text not null default 'CLP' check (moneda ~ '^[A-Z]{3}$'),
    version     integer not null default 1,
    sync_seq    bigint not null default 0,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    created_by  uuid,
    updated_by  uuid,
    deleted_at  timestamptz
);

create table public.miembros (
    negocio_id  uuid not null references public.negocios (id) on delete restrict,
    usuario_id  uuid not null references auth.users (id) on delete restrict,
    rol         public.rol_negocio not null,
    created_at  timestamptz not null default now(),
    created_by  uuid,
    updated_at  timestamptz not null default now(),
    primary key (negocio_id, usuario_id)
);
create index miembros_usuario_idx on public.miembros (usuario_id);

create table public.insumos (
    id                    uuid primary key default gen_random_uuid(),  -- el cliente envía su UUID
    negocio_id            uuid not null references public.negocios (id) on delete restrict,
    nombre                text not null check (btrim(nombre) <> ''),
    -- Datos de hoy, sin reinterpretar (D4/D6): los usa la fórmula actual
    unidad                text not null default '',
    precio                numeric(18, 6) not null default 0 check (precio >= 0),
    merma_pct             numeric(9, 6) not null default 0
                          check (merma_pct >= 0 and merma_pct < 1),   -- fracción: 0,1 = 10 % (como en la app)
    -- Inventario: solo con unidad base confirmada. Estas columnas las escribe el servidor.
    unidad_base           text references public.unidades (codigo)
                          check (unidad_base in ('g', 'ml', 'unidad')),
    stock_actual          numeric(18, 6) not null default 0,             -- puede ser negativo (con aviso)
    costo_promedio        numeric(18, 6) check (costo_promedio >= 0),    -- por unidad base, para contabilidad
    costo_reposicion      numeric(18, 6) check (costo_reposicion >= 0),  -- por unidad base, para cotizar
    costo_actualizado_en  timestamptz,                                   -- fecha del costo de reposición
    -- Sincronización
    version               integer not null default 1,
    sync_seq              bigint not null default 0,
    ultima_op             uuid,          -- UUID de la operación de la cola que hizo el último cambio
    created_at            timestamptz not null default now(),
    updated_at            timestamptz not null default now(),
    created_by            uuid,
    updated_by            uuid,
    deleted_at            timestamptz,
    unique (negocio_id, id),
    check (unidad_base is not null or (stock_actual = 0 and costo_promedio is null and costo_reposicion is null))
);

create table public.platos (
    id            uuid primary key default gen_random_uuid(),
    negocio_id    uuid not null references public.negocios (id) on delete restrict,
    nombre        text not null check (btrim(nombre) <> ''),
    precio_venta  numeric(18, 6) not null default 0 check (precio_venta >= 0),
    mano_obra     numeric(18, 6) not null default 0 check (mano_obra >= 0),
    imagen        text,          -- nombre del archivo; Supabase Storage queda para otra fase
    version       integer not null default 1,
    sync_seq      bigint not null default 0,
    ultima_op     uuid,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now(),
    created_by    uuid,
    updated_by    uuid,
    deleted_at    timestamptz,
    unique (negocio_id, id)
);

create table public.plato_insumos (
    id          uuid primary key default gen_random_uuid(),
    negocio_id  uuid not null,
    plato_id    uuid not null,
    insumo_id   uuid not null,
    cantidad    numeric(18, 6) not null check (cantidad >= 0),
    -- Unidad de la cantidad (D5). NULL = la unidad antigua del insumo, sin convertir:
    -- ese ingrediente no entra en el costo proyectado ni en la producción.
    unidad      text references public.unidades (codigo),
    version     integer not null default 1,
    sync_seq    bigint not null default 0,
    ultima_op   uuid,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    created_by  uuid,
    updated_by  uuid,
    deleted_at  timestamptz,
    -- Claves compuestas: una receta no puede apuntar a datos de otro negocio
    foreign key (negocio_id, plato_id)  references public.platos  (negocio_id, id) on delete restrict,
    foreign key (negocio_id, insumo_id) references public.insumos (negocio_id, id) on delete restrict
);
create index plato_insumos_plato_idx  on public.plato_insumos (plato_id);
create index plato_insumos_insumo_idx on public.plato_insumos (insumo_id);

-- Historial de compras: inmutable (sin UPDATE ni DELETE). Correcciones: pendiente.
create table public.compras_insumos (
    id                 uuid primary key default gen_random_uuid(),   -- UUID del cliente: idempotencia
    negocio_id         uuid not null,
    insumo_id          uuid not null,
    cantidad_comprada  numeric(18, 6) not null check (cantidad_comprada > 0),   -- en unidad base
    costo_total        numeric(18, 6) not null check (costo_total >= 0),
    costo_unitario     numeric(18, 6) generated always as (round(costo_total / nullif(cantidad_comprada, 0), 6)) stored,  -- nullif: que actúe el CHECK
    comprada_en        timestamptz not null default now(),
    sync_seq           bigint not null default 0,
    ultima_op          uuid,
    created_at         timestamptz not null default now(),
    created_by         uuid,
    foreign key (negocio_id, insumo_id) references public.insumos (negocio_id, id) on delete restrict
);
create index compras_insumo_idx on public.compras_insumos (insumo_id, comprada_en);

create table public.producciones (
    id            uuid primary key default gen_random_uuid(),
    negocio_id    uuid not null,
    plato_id      uuid not null,
    porciones     numeric(18, 6) not null check (porciones > 0),
    costo_total   numeric(18, 6),          -- suma de los consumos (costo promedio)
    producido_en  timestamptz not null default now(),
    sync_seq      bigint not null default 0,
    created_at    timestamptz not null default now(),
    created_by    uuid,
    foreign key (negocio_id, plato_id) references public.platos (negocio_id, id) on delete restrict
);

-- Consumos reales: descuentan stock y guardan el costo contable (costo promedio).
create table public.consumos_insumos (
    id                uuid primary key default gen_random_uuid(),
    negocio_id        uuid not null,
    insumo_id         uuid not null,
    produccion_id     uuid references public.producciones (id) on delete restrict,
    cantidad          numeric(18, 6) not null check (cantidad > 0),           -- en unidad base
    costo_unitario    numeric(18, 6),     -- costo promedio al momento; NULL si aún no hay compras
    costo_total       numeric(18, 6),
    stock_resultante  numeric(18, 6),
    stock_negativo    boolean not null default false,                         -- el aviso
    motivo            text not null default 'consumo' check (motivo in ('consumo', 'produccion', 'perdida', 'ajuste')),
    consumido_en      timestamptz not null default now(),
    sync_seq          bigint not null default 0,
    ultima_op         uuid,
    created_at        timestamptz not null default now(),
    created_by        uuid,
    foreign key (negocio_id, insumo_id) references public.insumos (negocio_id, id) on delete restrict
);
create index consumos_insumo_idx on public.consumos_insumos (insumo_id, consumido_en);

create index insumos_sync_idx       on public.insumos          (negocio_id, sync_seq);
create index platos_sync_idx        on public.platos           (negocio_id, sync_seq);
create index plato_insumos_sync_idx on public.plato_insumos    (negocio_id, sync_seq);
create index compras_sync_idx       on public.compras_insumos  (negocio_id, sync_seq);
create index consumos_sync_idx      on public.consumos_insumos (negocio_id, sync_seq);
create index producciones_sync_idx  on public.producciones     (negocio_id, sync_seq);

-- -----------------------------------------------------------------------------
-- Funciones auxiliares (esquema privado, no expuesto por la API)
-- -----------------------------------------------------------------------------

-- Rol del usuario autenticado en un negocio, o NULL si no es miembro.
-- security definer: lee miembros sin pasar por su propia RLS (evita recursión).
create function privado.rol_en(p_negocio uuid)
returns public.rol_negocio
language sql stable security definer set search_path = ''
as $$
    select m.rol from public.miembros m
    where m.negocio_id = p_negocio and m.usuario_id = (select auth.uid())
$$;

create function privado.puede_editar(p_negocio uuid)
returns boolean
language sql stable security definer set search_path = ''
as $$
    select coalesce(privado.rol_en(p_negocio) in ('propietario', 'administrador', 'editor'), false)
$$;

revoke all on function privado.rol_en(uuid), privado.puede_editar(uuid) from public;
grant execute on function privado.rol_en(uuid), privado.puede_editar(uuid) to authenticated;

-- -----------------------------------------------------------------------------
-- Triggers de los datos editables: columnas que fija el servidor y reglas que
-- RLS no puede expresar
-- -----------------------------------------------------------------------------

create function privado.antes_de_escribir()
returns trigger
language plpgsql security definer set search_path = ''
as $$
declare
    v_solo_inventario boolean := false;
begin
    if tg_op = 'INSERT' then
        new.version    := 1;
        new.created_at := now();
        new.created_by := auth.uid();
        new.deleted_at := null;          -- no se crean registros ya eliminados
    else
        if new.id <> old.id then
            raise exception 'No se puede cambiar el id' using errcode = '42501';
        end if;
        if tg_table_name <> 'negocios' then
            if new.negocio_id <> old.negocio_id then
                raise exception 'No se puede mover un registro a otro negocio' using errcode = '42501';
            end if;
        end if;
        -- Sin restauración (⏳ en 8.1): un registro eliminado no se edita ni se revive
        if old.deleted_at is not null then
            raise exception 'El registro está eliminado' using errcode = '42501';
        end if;
        if tg_table_name = 'insumos' then
            -- D4: no se cambia la unidad base de un insumo que ya la tiene
            if old.unidad_base is not null and new.unidad_base is distinct from old.unidad_base then
                raise exception 'La unidad base de un insumo no se cambia' using errcode = '42501';
            end if;
            -- Una compra o un consumo solo cambia el inventario: no sube la versión, para
            -- no provocar conflictos falsos con ediciones del nombre o del precio.
            v_solo_inventario :=
                (new.nombre, new.unidad, new.precio, new.merma_pct, new.unidad_base, new.deleted_at, new.ultima_op)
                is not distinct from
                (old.nombre, old.unidad, old.precio, old.merma_pct, old.unidad_base, old.deleted_at, old.ultima_op);
        end if;
        if new.deleted_at is not null and auth.uid() is not null then
            if tg_table_name = 'negocios' then
                -- Archivar o eliminar el negocio: procedimiento pendiente (⏳)
                raise exception 'Archivar un negocio aún no está permitido' using errcode = '42501';
            end if;
            -- Borrado lógico de insumos y platos: propietario y administrador (✅);
            -- editor ⏳ → denegado. Quitar un ingrediente de una receta es modificar
            -- la receta (✅ para el editor).
            if tg_table_name in ('insumos', 'platos')
               and coalesce(privado.rol_en(new.negocio_id)::text, '') not in ('propietario', 'administrador') then
                raise exception 'Tu rol no permite eliminar este registro' using errcode = '42501';
            end if;
            new.deleted_at := now();
        end if;
        new.version    := case when v_solo_inventario then old.version else old.version + 1 end;
        new.created_at := old.created_at;
        new.created_by := old.created_by;
    end if;
    new.updated_at := now();
    new.updated_by := auth.uid();
    new.sync_seq   := nextval('public.sync_seq');
    return new;
end
$$;

create trigger antes_de_escribir before insert or update on public.negocios
    for each row execute function privado.antes_de_escribir();
create trigger antes_de_escribir before insert or update on public.insumos
    for each row execute function privado.antes_de_escribir();
create trigger antes_de_escribir before insert or update on public.platos
    for each row execute function privado.antes_de_escribir();
create trigger antes_de_escribir before insert or update on public.plato_insumos
    for each row execute function privado.antes_de_escribir();

-- Un ingrediente activo solo puede apuntar a un plato y un insumo activos.
create function privado.validar_ingrediente()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
    if new.deleted_at is null then
        if exists (select 1 from public.platos p where p.id = new.plato_id and p.deleted_at is not null)
           or exists (select 1 from public.insumos i where i.id = new.insumo_id and i.deleted_at is not null) then
            raise exception 'El plato o el insumo de este ingrediente está eliminado' using errcode = '23503';
        end if;
    end if;
    if tg_op = 'UPDATE' and (new.plato_id <> old.plato_id or new.insumo_id <> old.insumo_id) then
        raise exception 'Un ingrediente no cambia de plato ni de insumo: se quita y se agrega otro'
            using errcode = '42501';
    end if;
    return new;
end
$$;

create trigger validar_ingrediente before insert or update on public.plato_insumos
    for each row execute function privado.validar_ingrediente();

-- Igual que hoy en la app: al eliminar un insumo o un plato, sus ingredientes se
-- eliminan también (lógicamente). Pendiente 8.10: cascada lógica o bloqueo.
create function privado.cascada_ingredientes()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
    if old.deleted_at is null and new.deleted_at is not null then
        if tg_table_name = 'insumos' then
            update public.plato_insumos set deleted_at = now()
            where insumo_id = new.id and deleted_at is null;
        else
            update public.plato_insumos set deleted_at = now()
            where plato_id = new.id and deleted_at is null;
        end if;
    end if;
    return null;
end
$$;

create trigger cascada_ingredientes after update on public.insumos
    for each row execute function privado.cascada_ingredientes();
create trigger cascada_ingredientes after update on public.platos
    for each row execute function privado.cascada_ingredientes();

-- -----------------------------------------------------------------------------
-- Inventario: compras, consumos y costos
-- -----------------------------------------------------------------------------

-- Bloquea el insumo (SELECT … FOR UPDATE) y comprueba que admite inventario.
-- Dos compras o consumos simultáneos del mismo insumo se aplican uno detrás del otro.
create function privado.bloquear_insumo(p_insumo uuid)
returns public.insumos
language plpgsql security definer set search_path = ''
as $$
declare
    v public.insumos;
begin
    select * into v from public.insumos where id = p_insumo for update;
    if not found then
        raise exception 'El insumo no existe' using errcode = '23503';
    end if;
    if v.deleted_at is not null then
        raise exception 'El insumo está eliminado' using errcode = '23503';
    end if;
    if v.unidad_base is null then
        raise exception 'El insumo "%" no tiene unidad base confirmada: no lleva inventario', v.nombre
            using errcode = '22023';
    end if;
    return v;
end
$$;

-- Columnas que fija el servidor en compras, consumos y producciones.
create function privado.antes_de_movimiento()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
    new.created_at := now();
    new.created_by := auth.uid();
    new.sync_seq   := nextval('public.sync_seq');
    -- if anidados: PL/pgSQL no corta el AND y cada tabla tiene columnas distintas
    if tg_table_name = 'compras_insumos' then
        if new.comprada_en > now() + interval '1 day' then
            raise exception 'La fecha de compra está en el futuro' using errcode = '22007';
        end if;
    end if;
    if tg_table_name = 'consumos_insumos' then
        if new.consumido_en > now() + interval '1 day' then
            raise exception 'La fecha de consumo está en el futuro' using errcode = '22007';
        end if;
        -- Solo una producción puede marcar consumos como 'produccion'
        if new.motivo = 'produccion' and new.produccion_id is null then
            raise exception 'Use registrar_produccion() para los consumos de producción' using errcode = '42501';
        end if;
    end if;
    return new;
end
$$;

create trigger antes_de_movimiento before insert on public.compras_insumos
    for each row execute function privado.antes_de_movimiento();
create trigger antes_de_movimiento before insert on public.consumos_insumos
    for each row execute function privado.antes_de_movimiento();
create trigger antes_de_movimiento before insert on public.producciones
    for each row execute function privado.antes_de_movimiento();

-- AFTER INSERT en compras: suma el stock, recalcula el costo promedio ponderado y
-- actualiza el costo de reposición.
--   costo_promedio nuevo = (stock × costo_promedio + costo_total) / (stock + cantidad)
--   Si el stock previo es 0 o negativo, o aún no hay costo, el promedio pasa a ser el
--   costo unitario de esta compra (no se valoriza un stock que no existe).
--   El costo de reposición solo se reemplaza si esta compra no es más antigua que el
--   costo vigente: una compra antigua registrada sin conexión no pisa un precio nuevo.
create function privado.aplicar_compra()
returns trigger
language plpgsql security definer set search_path = ''
as $$
declare
    v public.insumos;
begin
    v := privado.bloquear_insumo(new.insumo_id);
    update public.insumos set
        stock_actual   = v.stock_actual + new.cantidad_comprada,
        costo_promedio = case
            when v.stock_actual <= 0 or v.costo_promedio is null then new.costo_unitario
            else round((v.stock_actual * v.costo_promedio + new.costo_total)
                       / (v.stock_actual + new.cantidad_comprada), 6)
        end,
        costo_reposicion = case
            when v.costo_actualizado_en is null or new.comprada_en >= v.costo_actualizado_en
            then new.costo_unitario else v.costo_reposicion end,
        costo_actualizado_en = greatest(coalesce(v.costo_actualizado_en, new.comprada_en), new.comprada_en)
    where id = new.insumo_id;
    return null;
end
$$;

create trigger aplicar_compra after insert on public.compras_insumos
    for each row execute function privado.aplicar_compra();

-- BEFORE INSERT en consumos: descuenta el stock y registra el costo contable con el
-- costo promedio vigente. Si el stock queda negativo se permite y se marca el aviso.
create function privado.aplicar_consumo()
returns trigger
language plpgsql security definer set search_path = ''
as $$
declare
    v public.insumos;
begin
    v := privado.bloquear_insumo(new.insumo_id);
    new.costo_unitario   := v.costo_promedio;
    new.costo_total      := round(new.cantidad * v.costo_promedio, 6);
    new.stock_resultante := v.stock_actual - new.cantidad;
    new.stock_negativo   := new.stock_resultante < 0;
    update public.insumos set stock_actual = new.stock_resultante where id = new.insumo_id;
    return new;
end
$$;

-- Se ejecuta después de antes_de_movimiento (los triggers BEFORE van por orden alfabético)
create trigger b_aplicar_consumo before insert on public.consumos_insumos
    for each row execute function privado.aplicar_consumo();

-- Actualización manual de mercado: cambia solo el costo de reposición y su fecha,
-- sin compra física. Mismo criterio de fechas que las compras.
create function public.actualizar_costo_reposicion(
    p_insumo uuid, p_costo_unitario numeric, p_vigente_desde timestamptz default now())
returns public.insumos
language plpgsql security definer set search_path = ''
as $$
declare
    v public.insumos;
begin
    if p_costo_unitario is null or p_costo_unitario < 0 then
        raise exception 'El costo debe ser cero o positivo' using errcode = '23514';
    end if;
    if p_vigente_desde > now() + interval '1 day' then
        raise exception 'La fecha está en el futuro' using errcode = '22007';
    end if;
    v := privado.bloquear_insumo(p_insumo);
    if not privado.puede_editar(v.negocio_id) then
        raise exception 'Tu rol no permite actualizar precios' using errcode = '42501';
    end if;
    if v.costo_actualizado_en is null or p_vigente_desde >= v.costo_actualizado_en then
        update public.insumos
        set costo_reposicion = round(p_costo_unitario, 6), costo_actualizado_en = p_vigente_desde
        where id = p_insumo
        returning * into v;
    end if;
    return v;
end
$$;

-- Producción: descuenta cada ingrediente de la receta según las porciones.
--   cantidad consumida = cantidad × factor de su unidad × porciones × (1 + merma_pct)
-- Exige que todos los ingredientes tengan unidad y que sea de la misma dimensión que la
-- unidad base del insumo (D4: no se convierte masa en volumen). Idempotente por p_id.
create function public.registrar_produccion(
    p_id uuid, p_plato uuid, p_porciones numeric, p_producido_en timestamptz default now())
returns public.producciones
language plpgsql security definer set search_path = ''
as $$
declare
    v_plato  public.platos;
    v_prod   public.producciones;
    r        record;
    v_total  numeric := 0;
    v_costo  numeric;
    v_sin_costo boolean := false;
begin
    select * into v_prod from public.producciones where id = p_id;
    if found then
        if privado.rol_en(v_prod.negocio_id) is null then
            raise exception 'La producción no existe' using errcode = '23503';
        end if;
        return v_prod;                              -- reintento: ya estaba aplicada
    end if;
    select * into v_plato from public.platos where id = p_plato and deleted_at is null;
    if not found then
        raise exception 'El plato no existe' using errcode = '23503';
    end if;
    if not privado.puede_editar(v_plato.negocio_id) then
        raise exception 'Tu rol no permite registrar producciones' using errcode = '42501';
    end if;
    if exists (
        select 1 from public.plato_insumos pi
        join public.insumos i on i.id = pi.insumo_id
        left join public.unidades u on u.codigo = pi.unidad
        left join public.unidades b on b.codigo = i.unidad_base
        where pi.plato_id = p_plato and pi.deleted_at is null
          and (pi.unidad is null or i.unidad_base is null or u.dimension <> b.dimension)
    ) then
        raise exception 'Hay ingredientes sin unidad confirmada o con unidades incompatibles'
            using errcode = '22023';
    end if;

    insert into public.producciones (id, negocio_id, plato_id, porciones, producido_en)
    values (p_id, v_plato.negocio_id, p_plato, p_porciones, p_producido_en)
    returning * into v_prod;

    for r in
        select pi.insumo_id,
               round(pi.cantidad * u.factor * p_porciones * (1 + i.merma_pct), 6) as cantidad
        from public.plato_insumos pi
        join public.insumos i on i.id = pi.insumo_id
        join public.unidades u on u.codigo = pi.unidad
        where pi.plato_id = p_plato and pi.deleted_at is null and pi.cantidad > 0
        order by pi.insumo_id                       -- orden fijo de bloqueo: evita interbloqueos
    loop
        insert into public.consumos_insumos
            (negocio_id, insumo_id, produccion_id, cantidad, motivo, consumido_en)
        values (v_plato.negocio_id, r.insumo_id, p_id, r.cantidad, 'produccion', p_producido_en)
        returning costo_total into v_costo;
        if v_costo is null then
            v_sin_costo := true;
        else
            v_total := v_total + v_costo;
        end if;
    end loop;

    update public.producciones
    set costo_total = case when v_sin_costo then null else v_total end
    where id = p_id
    returning * into v_prod;
    return v_prod;
end
$$;

revoke all on function public.actualizar_costo_reposicion(uuid, numeric, timestamptz) from public, anon;
revoke all on function public.registrar_produccion(uuid, uuid, numeric, timestamptz) from public, anon;
grant execute on function public.actualizar_costo_reposicion(uuid, numeric, timestamptz) to authenticated;
grant execute on function public.registrar_produccion(uuid, uuid, numeric, timestamptz) to authenticated;

-- Vista para el cotizador: alerta de precio desactualizado (> 30 días) y de stock negativo.
-- security_invoker: aplica la RLS de quien consulta.
create view public.insumos_costos with (security_invoker = true) as
select i.id, i.negocio_id, i.nombre, i.unidad_base, i.stock_actual,
       i.costo_promedio, i.costo_reposicion, i.costo_actualizado_en,
       i.costo_reposicion is null                                   as sin_costo_reposicion,
       coalesce(i.costo_actualizado_en < now() - interval '30 days', false) as costo_desactualizado,
       i.stock_actual < 0                                           as stock_negativo
from public.insumos i
where i.deleted_at is null;

-- -----------------------------------------------------------------------------
-- Miembros: protecciones de D1
--   * todo negocio conserva al menos un propietario;
--   * nadie asigna el rol propietario fuera de la transferencia (pendiente ⏳),
--     salvo al crear el negocio (lo hace public.crear_negocio).
-- -----------------------------------------------------------------------------

create function privado.proteger_miembros()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
    if tg_op = 'INSERT' then
        if new.rol = 'propietario' and (
               new.usuario_id is distinct from auth.uid()
            or exists (select 1 from public.miembros m where m.negocio_id = new.negocio_id)
            or (select n.created_by from public.negocios n where n.id = new.negocio_id) is distinct from auth.uid()
        ) then
            raise exception 'El rol propietario solo se asigna al crear el negocio o por transferencia'
                using errcode = '42501';
        end if;
        new.created_at := now();
        new.created_by := auth.uid();
        new.updated_at := now();
        return new;
    end if;

    if tg_op = 'UPDATE' then
        if new.negocio_id <> old.negocio_id or new.usuario_id <> old.usuario_id then
            raise exception 'Solo se puede cambiar el rol' using errcode = '42501';
        end if;
        if new.rol = 'propietario' and old.rol <> 'propietario' then
            raise exception 'El rol propietario solo se asigna por transferencia' using errcode = '42501';
        end if;
        new.created_at := old.created_at;
        new.created_by := old.created_by;
        new.updated_at := now();
    end if;

    -- UPDATE que quita el rol propietario, o DELETE de un propietario
    if old.rol = 'propietario' and (tg_op = 'DELETE' or new.rol <> 'propietario') then
        if not exists (
            select 1 from public.miembros m
            where m.negocio_id = old.negocio_id and m.rol = 'propietario' and m.usuario_id <> old.usuario_id
        ) then
            raise exception 'El negocio debe conservar al menos un propietario' using errcode = '42501';
        end if;
    end if;

    if tg_op = 'DELETE' then
        return old;
    end if;
    return new;
end
$$;

create trigger proteger_miembros before insert or update or delete on public.miembros
    for each row execute function privado.proteger_miembros();

-- Crear un negocio: el usuario autenticado queda como su propietario.
create function public.crear_negocio(p_nombre text, p_moneda text default 'CLP')
returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
    v_id uuid;
begin
    if auth.uid() is null then
        raise exception 'Hay que iniciar sesión para crear un negocio' using errcode = '42501';
    end if;
    insert into public.negocios (nombre, moneda) values (p_nombre, p_moneda) returning id into v_id;
    insert into public.miembros (negocio_id, usuario_id, rol) values (v_id, auth.uid(), 'propietario');
    return v_id;
end
$$;

revoke all on function public.crear_negocio(text, text) from public, anon;
grant execute on function public.crear_negocio(text, text) to authenticated;

-- Las funciones de trigger no se llaman directamente
revoke all on function privado.antes_de_escribir(), privado.validar_ingrediente(),
    privado.cascada_ingredientes(), privado.bloquear_insumo(uuid), privado.antes_de_movimiento(),
    privado.aplicar_compra(), privado.aplicar_consumo(), privado.proteger_miembros() from public;

-- -----------------------------------------------------------------------------
-- Permisos de tabla y RLS
-- -----------------------------------------------------------------------------

-- Supabase da por defecto todos los permisos a anon y authenticated: se quitan y se
-- conceden solo los necesarios, por columna. El cliente nunca escribe version, fechas,
-- autoría, sync_seq, stock ni costos. Nadie borra filas físicamente (8.1).
revoke all on public.unidades, public.negocios, public.miembros, public.insumos, public.platos,
    public.plato_insumos, public.compras_insumos, public.producciones, public.consumos_insumos,
    public.insumos_costos
    from anon, authenticated;
revoke all on sequence public.sync_seq from anon, authenticated;

grant select on public.unidades, public.insumos_costos to authenticated;

grant select on public.negocios to authenticated;
grant update (nombre, moneda) on public.negocios to authenticated;

grant select, delete on public.miembros to authenticated;
grant insert (negocio_id, usuario_id, rol) on public.miembros to authenticated;
grant update (rol) on public.miembros to authenticated;

grant select on public.insumos, public.platos, public.plato_insumos,
    public.compras_insumos, public.producciones, public.consumos_insumos to authenticated;
grant insert (id, negocio_id, nombre, unidad, precio, merma_pct, unidad_base, ultima_op)
    on public.insumos to authenticated;
grant update (nombre, unidad, precio, merma_pct, unidad_base, deleted_at, ultima_op)
    on public.insumos to authenticated;
grant insert (id, negocio_id, nombre, precio_venta, mano_obra, imagen, ultima_op)
    on public.platos to authenticated;
grant update (nombre, precio_venta, mano_obra, imagen, deleted_at, ultima_op)
    on public.platos to authenticated;
grant insert (id, negocio_id, plato_id, insumo_id, cantidad, unidad, ultima_op)
    on public.plato_insumos to authenticated;
grant update (cantidad, unidad, deleted_at, ultima_op)
    on public.plato_insumos to authenticated;
grant insert (id, negocio_id, insumo_id, cantidad_comprada, costo_total, comprada_en, ultima_op)
    on public.compras_insumos to authenticated;
grant insert (id, negocio_id, insumo_id, cantidad, motivo, consumido_en, ultima_op)
    on public.consumos_insumos to authenticated;
-- producciones: solo mediante public.registrar_produccion()

alter table public.unidades         enable row level security;
alter table public.negocios         enable row level security;
alter table public.miembros         enable row level security;
alter table public.insumos          enable row level security;
alter table public.platos           enable row level security;
alter table public.plato_insumos    enable row level security;
alter table public.compras_insumos  enable row level security;
alter table public.producciones     enable row level security;
alter table public.consumos_insumos enable row level security;

create policy unidades_ver on public.unidades for select to authenticated using (true);

-- Negocios: los ven sus miembros; solo el propietario edita nombre y moneda.
create policy negocios_ver on public.negocios for select to authenticated
    using (privado.rol_en(id) is not null);
create policy negocios_editar on public.negocios for update to authenticated
    using (privado.rol_en(id) = 'propietario')
    with check (privado.rol_en(id) = 'propietario');

-- Miembros:
--   ver la lista: propietario y administrador (✅); cada uno ve siempre su propia fila
--   agregar: propietario (cualquier rol salvo propietario); administrador solo
--            editores y lectores (crear administradores ⏳ → no)
--   cambiar roles y quitar: propietario (✅); administrador ➜/⏳ → no
create policy miembros_ver on public.miembros for select to authenticated
    using (usuario_id = (select auth.uid())
           or privado.rol_en(negocio_id) in ('propietario', 'administrador'));
create policy miembros_agregar on public.miembros for insert to authenticated
    with check (
        (privado.rol_en(negocio_id) = 'propietario' and rol <> 'propietario')
        or (privado.rol_en(negocio_id) = 'administrador' and rol in ('editor', 'lector'))
    );
create policy miembros_cambiar_rol on public.miembros for update to authenticated
    using (privado.rol_en(negocio_id) = 'propietario')
    with check (privado.rol_en(negocio_id) = 'propietario');
create policy miembros_quitar on public.miembros for delete to authenticated
    using (privado.rol_en(negocio_id) = 'propietario');

-- Datos del negocio: todos los miembros los ven (también los eliminados, para que la
-- sincronización se entere de los borrados); propietario, administrador y editor crean
-- y modifican; el lector no tiene ninguna política de escritura.
create policy insumos_ver on public.insumos for select to authenticated
    using (privado.rol_en(negocio_id) is not null);
create policy insumos_crear on public.insumos for insert to authenticated
    with check (privado.puede_editar(negocio_id));
create policy insumos_modificar on public.insumos for update to authenticated
    using (privado.puede_editar(negocio_id)) with check (privado.puede_editar(negocio_id));

create policy platos_ver on public.platos for select to authenticated
    using (privado.rol_en(negocio_id) is not null);
create policy platos_crear on public.platos for insert to authenticated
    with check (privado.puede_editar(negocio_id));
create policy platos_modificar on public.platos for update to authenticated
    using (privado.puede_editar(negocio_id)) with check (privado.puede_editar(negocio_id));

create policy plato_insumos_ver on public.plato_insumos for select to authenticated
    using (privado.rol_en(negocio_id) is not null);
create policy plato_insumos_crear on public.plato_insumos for insert to authenticated
    with check (privado.puede_editar(negocio_id));
create policy plato_insumos_modificar on public.plato_insumos for update to authenticated
    using (privado.puede_editar(negocio_id)) with check (privado.puede_editar(negocio_id));

-- Compras (D1.1: también el editor) y consumos (aprobado: propietario, administrador y
-- editor; el lector solo consulta). Inmutables: sin políticas de UPDATE ni DELETE.
create policy compras_ver on public.compras_insumos for select to authenticated
    using (privado.rol_en(negocio_id) is not null);
create policy compras_registrar on public.compras_insumos for insert to authenticated
    with check (privado.puede_editar(negocio_id));

create policy consumos_ver on public.consumos_insumos for select to authenticated
    using (privado.rol_en(negocio_id) is not null);
create policy consumos_registrar on public.consumos_insumos for insert to authenticated
    with check (privado.puede_editar(negocio_id));

create policy producciones_ver on public.producciones for select to authenticated
    using (privado.rol_en(negocio_id) is not null);
