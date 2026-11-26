-- DOWN de 20261127000000_ventas_precios.sql
-- Se ejecuta a mano y SOLO en desarrollo: BORRA LAS VENTAS y los datos de precio de venta.
-- Deja el esquema como estaba tras 20261126000000_esquema_inicial.sql.
begin;
drop view if exists public.insumos_costos;
drop table if exists public.ventas;
drop function if exists public.fijar_precio_venta(uuid, numeric);
drop trigger if exists c_precio_sugerido on public.insumos;
drop trigger if exists recalcular_sugeridos on public.negocios;
drop function if exists privado.aplicar_venta(), privado.calcular_precio_sugerido(),
    privado.recalcular_sugeridos_negocio(), privado.margen_real(numeric, numeric, numeric),
    privado.precio_sugerido(numeric, numeric, numeric);

-- Versión original de la función (sin los campos de venta)
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

alter table public.insumos
    drop column se_vende, drop column margen_objetivo, drop column precio_venta,
    drop column precio_sugerido, drop column precio_actualizado_en;
alter table public.negocios drop column tasa_iva, drop column dias_alerta_precio;

-- Unidades de longitud: falla a propósito si algún insumo o receta las usa
alter table public.insumos drop constraint insumos_unidad_base_check;
alter table public.insumos add constraint insumos_unidad_base_check
    check (unidad_base in ('g', 'ml', 'unidad'));
delete from public.unidades where codigo in ('cm', 'm');
alter table public.unidades drop constraint unidades_dimension_check;
alter table public.unidades add constraint unidades_dimension_check
    check (dimension in ('masa', 'volumen', 'conteo'));

-- Vista original
create view public.insumos_costos with (security_invoker = true) as
select i.id, i.negocio_id, i.nombre, i.unidad_base, i.stock_actual,
       i.costo_promedio, i.costo_reposicion, i.costo_actualizado_en,
       i.costo_reposicion is null                                   as sin_costo_reposicion,
       coalesce(i.costo_actualizado_en < now() - interval '30 days', false) as costo_desactualizado,
       i.stock_actual < 0                                           as stock_negativo
from public.insumos i
where i.deleted_at is null;
revoke all on public.insumos_costos from anon, authenticated;
grant select on public.insumos_costos to authenticated;
commit;
