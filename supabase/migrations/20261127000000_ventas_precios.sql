-- =============================================================================
-- SmartCost: venta directa de productos, precio de venta y protección del margen
--
-- Amplía 20261126000000_esquema_inicial.sql (inventario de insumos) para que un
-- artículo se pueda vender directo, como en una tienda, almacén o ferretería.
-- La tabla `insumos` es el equivalente de `productos`: un artículo puede comprarse,
-- usarse en recetas, venderse directo o las tres cosas.
--
-- Decisiones del autor (2026-11-27):
--   * margen_objetivo en PORCENTAJE (30.00 = 30 %), igual que el margen que ya
--     calcula la app. Es margen sobre el precio, no recargo sobre el costo:
--       precio neto sugerido = costo de reposición / (1 − margen / 100)
--   * Los costos se registran NETOS (más flete); el precio al público incluye IVA:
--       precio sugerido = precio neto × (1 + tasa de IVA), redondeado HACIA ARRIBA a $10
--   * El precio de venta NUNCA cambia solo: el servidor calcula el sugerido y marca
--     "margen bajo"; el propietario o el administrador aprueban el precio nuevo.
--   * La alerta de precio desactualizado usa un umbral por negocio (30 días por defecto).
--   * Las ventas descuentan stock y registran el costo de venta al COSTO PROMEDIO.
--
-- Reversión: supabase/rollback/20261127000000_ventas_precios.down.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Unidades de longitud (ferretería: cables, mangueras, cadenas…)
-- -----------------------------------------------------------------------------

alter table public.unidades drop constraint unidades_dimension_check;
alter table public.unidades add constraint unidades_dimension_check
    check (dimension in ('masa', 'volumen', 'conteo', 'longitud'));
insert into public.unidades (codigo, nombre, dimension, unidad_base, factor) values
    ('m',  'metro',       'longitud', 'm', 1),
    ('cm', 'centímetro',  'longitud', 'm', 0.01);

alter table public.insumos drop constraint insumos_unidad_base_check;
alter table public.insumos add constraint insumos_unidad_base_check
    check (unidad_base in ('g', 'ml', 'unidad', 'm'));

-- -----------------------------------------------------------------------------
-- Ajustes del negocio
-- -----------------------------------------------------------------------------

alter table public.negocios
    add column tasa_iva numeric(5, 4) not null default 0.19 check (tasa_iva >= 0 and tasa_iva < 1),
    add column dias_alerta_precio integer not null default 30 check (dias_alerta_precio between 1 and 365);

-- Solo el propietario edita el negocio (política negocios_editar)
grant update (tasa_iva, dias_alerta_precio) on public.negocios to authenticated;

-- -----------------------------------------------------------------------------
-- Productos que se venden
-- -----------------------------------------------------------------------------

alter table public.insumos
    add column se_vende              boolean not null default false,
    add column margen_objetivo       numeric(5, 2) check (margen_objetivo >= 0 and margen_objetivo < 100),
    add column precio_venta          numeric(18, 2) check (precio_venta >= 0),     -- en góndola, con IVA
    add column precio_sugerido       numeric(18, 2),                               -- lo calcula el servidor
    add column precio_actualizado_en timestamptz;                                  -- cuándo se aprobó el precio

-- El cliente marca si se vende y su margen; el precio de góndola solo cambia con
-- public.fijar_precio_venta() (propietario o administrador).
grant insert (se_vende, margen_objetivo) on public.insumos to authenticated;
grant update (se_vende, margen_objetivo) on public.insumos to authenticated;

-- Precio sugerido con IVA, redondeado hacia arriba a $10. NULL si falta algún dato.
create function privado.precio_sugerido(p_costo numeric, p_margen numeric, p_iva numeric)
returns numeric
language sql immutable set search_path = ''
as $$
    select case
        when p_costo is null or p_margen is null or p_iva is null then null
        -- IVA antes de dividir y redondeo a 6 decimales antes de subir a $10: así una división
        -- periódica (500 / 0,7 = 714,2857…) no deja un residuo que convierta $850 en $860
        else ceil(round(p_costo * (1 + p_iva) / (1 - p_margen / 100), 6) / 10) * 10
    end
$$;

-- Margen real (%) de un precio con IVA frente al costo de reposición neto.
create function privado.margen_real(p_precio numeric, p_costo numeric, p_iva numeric)
returns numeric
language sql immutable set search_path = ''
as $$
    select case
        when p_precio is null or p_precio <= 0 or p_costo is null then null
        else round((p_precio / (1 + p_iva) - p_costo) / (p_precio / (1 + p_iva)) * 100, 2)
    end
$$;

-- Ahora los cambios de venta (se_vende, margen, precio aprobado) son ediciones del
-- usuario: suben la versión. El resto de la función es igual a la de la migración inicial.
create or replace function privado.antes_de_escribir()
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
            -- Compras, consumos, ventas y el precio sugerido solo cambian datos que calcula
            -- el servidor: no suben la versión (sin conflictos falsos entre dispositivos).
            v_solo_inventario :=
                (new.nombre, new.unidad, new.precio, new.merma_pct, new.unidad_base, new.deleted_at, new.ultima_op,
                 new.se_vende, new.margen_objetivo, new.precio_venta)
                is not distinct from
                (old.nombre, old.unidad, old.precio, old.merma_pct, old.unidad_base, old.deleted_at, old.ultima_op,
                 old.se_vende, old.margen_objetivo, old.precio_venta);
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

-- Recalcula el precio sugerido cada vez que cambia el costo de reposición, el margen o
-- si se vende: con compras, listas de proveedor y ediciones. Nunca toca precio_venta.
-- (Se llama "c_…" para ejecutarse después de antes_de_escribir: los triggers BEFORE van por
-- orden alfabético.)
create function privado.calcular_precio_sugerido()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
    if new.se_vende then
        new.precio_sugerido := privado.precio_sugerido(
            new.costo_reposicion, new.margen_objetivo,
            (select n.tasa_iva from public.negocios n where n.id = new.negocio_id));
    else
        new.precio_sugerido := null;
    end if;
    return new;
end
$$;

create trigger c_precio_sugerido before insert or update on public.insumos
    for each row execute function privado.calcular_precio_sugerido();

-- Si cambia la tasa de IVA del negocio, se recalculan los sugeridos de sus productos.
create function privado.recalcular_sugeridos_negocio()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
    if new.tasa_iva is distinct from old.tasa_iva then
        update public.insumos set margen_objetivo = margen_objetivo
        where negocio_id = new.id and se_vende and deleted_at is null;
    end if;
    return null;
end
$$;

create trigger recalcular_sugeridos after update on public.negocios
    for each row execute function privado.recalcular_sugeridos_negocio();

-- Aprobar el precio de góndola: el sugerido (por defecto) u otro que decida el dueño.
create function public.fijar_precio_venta(p_insumo uuid, p_precio numeric default null)
returns public.insumos
language plpgsql security definer set search_path = ''
as $$
declare
    v public.insumos;
    v_precio numeric;
begin
    select * into v from public.insumos where id = p_insumo and deleted_at is null for update;
    if not found or privado.rol_en(v.negocio_id) is null then
        raise exception 'El producto no existe' using errcode = '23503';
    end if;
    if coalesce(privado.rol_en(v.negocio_id)::text, '') not in ('propietario', 'administrador') then
        raise exception 'Solo el propietario o el administrador aprueban precios' using errcode = '42501';
    end if;
    if not v.se_vende then
        raise exception 'El producto "%" no está marcado para la venta', v.nombre using errcode = '22023';
    end if;
    v_precio := coalesce(p_precio, v.precio_sugerido);
    if v_precio is null then
        raise exception 'Falta el costo o el margen para sugerir un precio: indícalo a mano' using errcode = '22023';
    end if;
    if v_precio < 0 then
        raise exception 'El precio no puede ser negativo' using errcode = '23514';
    end if;
    update public.insumos set precio_venta = round(v_precio, 2), precio_actualizado_en = now()
    where id = p_insumo
    returning * into v;
    return v;
end
$$;

revoke all on function public.fijar_precio_venta(uuid, numeric) from public, anon;
grant execute on function public.fijar_precio_venta(uuid, numeric) to authenticated;

-- -----------------------------------------------------------------------------
-- Ventas: descuentan stock y registran el costo de venta al costo promedio
-- -----------------------------------------------------------------------------

create table public.ventas (
    id                uuid primary key default gen_random_uuid(),     -- UUID del cliente: idempotencia
    negocio_id        uuid not null,
    insumo_id         uuid not null,
    cantidad          numeric(18, 6) not null check (cantidad > 0),   -- en unidad base de venta
    precio_unitario   numeric(18, 2) check (precio_unitario >= 0),    -- cobrado, con IVA (por defecto, el de góndola)
    total             numeric(18, 2),                                 -- cobrado, con IVA
    ingreso_neto      numeric(18, 6),                                 -- total sin IVA
    costo_unitario    numeric(18, 6),                                 -- costo promedio al vender; NULL si no hay compras
    costo_venta       numeric(18, 6),
    utilidad          numeric(18, 6),                                 -- ingreso neto − costo de venta
    stock_resultante  numeric(18, 6),
    stock_negativo    boolean not null default false,                 -- el aviso
    vendido_en        timestamptz not null default now(),
    sync_seq          bigint not null default 0,
    ultima_op         uuid,
    created_at        timestamptz not null default now(),
    created_by        uuid,
    foreign key (negocio_id, insumo_id) references public.insumos (negocio_id, id) on delete restrict
);
create index ventas_insumo_idx on public.ventas (insumo_id, vendido_en);
create index ventas_sync_idx on public.ventas (negocio_id, sync_seq);

create function privado.aplicar_venta()
returns trigger
language plpgsql security definer set search_path = ''
as $$
declare
    v public.insumos;
    v_iva numeric;
begin
    new.created_at := now();
    new.created_by := auth.uid();
    new.sync_seq   := nextval('public.sync_seq');
    if new.vendido_en > now() + interval '1 day' then
        raise exception 'La fecha de venta está en el futuro' using errcode = '22007';
    end if;
    v := privado.bloquear_insumo(new.insumo_id);           -- SELECT … FOR UPDATE
    if not v.se_vende then
        raise exception 'El producto "%" no está marcado para la venta', v.nombre using errcode = '22023';
    end if;
    new.precio_unitario := coalesce(new.precio_unitario, v.precio_venta);
    if new.precio_unitario is null then
        raise exception 'El producto "%" no tiene precio de venta aprobado', v.nombre using errcode = '22023';
    end if;
    select n.tasa_iva into v_iva from public.negocios n where n.id = v.negocio_id;
    new.total            := round(new.cantidad * new.precio_unitario, 2);
    new.ingreso_neto     := round(new.total / (1 + v_iva), 6);
    new.costo_unitario   := v.costo_promedio;
    new.costo_venta      := round(new.cantidad * v.costo_promedio, 6);
    new.utilidad         := new.ingreso_neto - new.costo_venta;
    new.stock_resultante := v.stock_actual - new.cantidad;
    new.stock_negativo   := new.stock_resultante < 0;
    update public.insumos set stock_actual = new.stock_resultante where id = new.insumo_id;
    return new;
end
$$;

create trigger aplicar_venta before insert on public.ventas
    for each row execute function privado.aplicar_venta();

revoke all on function privado.precio_sugerido(numeric, numeric, numeric), privado.margen_real(numeric, numeric, numeric),
    privado.calcular_precio_sugerido(), privado.recalcular_sugeridos_negocio(), privado.aplicar_venta() from public;
grant execute on function privado.margen_real(numeric, numeric, numeric) to authenticated;  -- la usa la vista

revoke all on public.ventas from anon, authenticated;
grant select on public.ventas to authenticated;
grant insert (id, negocio_id, insumo_id, cantidad, precio_unitario, vendido_en, ultima_op)
    on public.ventas to authenticated;
alter table public.ventas enable row level security;

-- Registran ventas: propietario, administrador y editor; el lector solo consulta.
-- Inmutables: sin UPDATE ni DELETE (anular una venta: pendiente).
create policy ventas_ver on public.ventas for select to authenticated
    using (privado.rol_en(negocio_id) is not null);
create policy ventas_registrar on public.ventas for insert to authenticated
    with check (privado.puede_editar(negocio_id));

-- -----------------------------------------------------------------------------
-- Vista para el cotizador y la sala de ventas
-- -----------------------------------------------------------------------------

-- Las columnas existentes se conservan en su orden; las nuevas van al final.
-- costo_desactualizado ahora usa el umbral del negocio (30 días por defecto).
create or replace view public.insumos_costos with (security_invoker = true) as
select i.id, i.negocio_id, i.nombre, i.unidad_base, i.stock_actual,
       i.costo_promedio, i.costo_reposicion, i.costo_actualizado_en,
       i.costo_reposicion is null                                   as sin_costo_reposicion,
       coalesce(i.costo_actualizado_en < now() - make_interval(days => n.dias_alerta_precio), false)
                                                                    as costo_desactualizado,
       i.stock_actual < 0                                           as stock_negativo,
       i.se_vende, i.margen_objetivo, i.precio_venta, i.precio_sugerido, i.precio_actualizado_en,
       privado.margen_real(i.precio_venta, i.costo_reposicion, n.tasa_iva) as margen_real,
       coalesce(i.se_vende and privado.margen_real(i.precio_venta, i.costo_reposicion, n.tasa_iva)
                < i.margen_objetivo, false)                         as margen_bajo,
       coalesce(i.se_vende and i.precio_venta is null and i.precio_sugerido is not null, false)
                                                                    as sin_precio_venta
from public.insumos i
join public.negocios n on n.id = i.negocio_id
where i.deleted_at is null;
