-- Pruebas de inventario y costos (pgTAP). Se revierte todo al final.
--
-- Caso pedido: un saco de 25 kg de harina, consumo parcial, y una segunda compra más
-- cara antes de agotar el stock. Valores esperados calculados a mano:
--
--   compra 1  25.000 g por $25.000  → costo unitario 1,000000 $/g
--             stock 25.000 · promedio 1,000000 · reposición 1,000000
--   consumo   10.000 g              → costo contable 10.000 (promedio 1,0)
--             stock 15.000
--   compra 2  25.000 g por $30.000  → costo unitario 1,200000 $/g
--             promedio (15.000 × 1,0 + 30.000) / 40.000 = 1,125000
--             reposición 1,200000 (la cotización usa el precio nuevo)
begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

select plan(38);

insert into auth.users (id) values
    ('00000000-0000-4000-8000-000000000001'),  -- propietario
    ('00000000-0000-4000-8000-000000000003'),  -- editor
    ('00000000-0000-4000-8000-000000000004');  -- lector

create schema pruebas;
grant usage on schema pruebas to authenticated;
create function pruebas.como(p_usuario uuid) returns void language plpgsql as $$
begin
    perform set_config('request.jwt.claims',
                       json_build_object('sub', p_usuario, 'role', 'authenticated')::text, true);
    -- Formato antiguo, que usa la imagen base de Postgres de Supabase en auth.uid()
    perform set_config('request.jwt.claim.sub', p_usuario::text, true);
    perform set_config('role', 'authenticated', true);
end $$;
create table pruebas.ids (clave text primary key, id uuid);
grant select, insert on pruebas.ids to authenticated;
create function pruebas.id(p text) returns uuid language sql stable as $$
    select id from pruebas.ids where clave = p
$$;
create function pruebas.insumo(p text) returns public.insumos language sql stable as $$
    select * from public.insumos where id = pruebas.id(p)
$$;

create function pruebas.consumir(p text, p_cantidad numeric) returns public.consumos_insumos
language plpgsql as $$
declare r public.consumos_insumos;
begin
    insert into public.consumos_insumos (negocio_id, insumo_id, cantidad)
    values (pruebas.id('negocio'), pruebas.id(p), p_cantidad) returning * into r;
    return r;
end $$;

select pruebas.como('00000000-0000-4000-8000-000000000001');
insert into pruebas.ids values ('negocio', public.crear_negocio('Panadería de prueba'));
insert into public.miembros (negocio_id, usuario_id, rol) values
    (pruebas.id('negocio'), '00000000-0000-4000-8000-000000000003', 'editor'),
    (pruebas.id('negocio'), '00000000-0000-4000-8000-000000000004', 'lector');

-- ---------- el editor registra insumos y compras (D1.1) ----------
select pruebas.como('00000000-0000-4000-8000-000000000003');
insert into pruebas.ids values ('harina', gen_random_uuid()), ('aceite', gen_random_uuid()),
                               ('sin_base', gen_random_uuid()), ('c1', gen_random_uuid());
insert into public.insumos (id, negocio_id, nombre, unidad, merma_pct, unidad_base) values
    (pruebas.id('harina'),   pruebas.id('negocio'), 'Harina',  '25kg', 0.1, 'g'),   -- merma 10 %
    (pruebas.id('aceite'),   pruebas.id('negocio'), 'Aceite',  'lt',    0, 'ml'),
    (pruebas.id('sin_base'), pruebas.id('negocio'), 'Comino',  '10kg',  0, null);

insert into public.compras_insumos (id, negocio_id, insumo_id, cantidad_comprada, costo_total)
values (pruebas.id('c1'), pruebas.id('negocio'), pruebas.id('harina'), 25000, 25000);

select is((select costo_unitario from public.compras_insumos where id = pruebas.id('c1')), 1.000000::numeric,
          'compra 1: costo unitario generado = costo_total / cantidad');
select is((pruebas.insumo('harina')).stock_actual, 25000::numeric, 'compra 1: stock 25.000 g');
select is((pruebas.insumo('harina')).costo_promedio, 1::numeric, 'compra 1: promedio 1,0');
select is((pruebas.insumo('harina')).costo_reposicion, 1::numeric, 'compra 1: reposición 1,0');

-- ---------- consumo intermedio ----------
select is((pruebas.consumir('harina', 10000)).costo_total, 10000::numeric, 'consumo de 10.000 g valorizado al promedio (1,0)');
select is((pruebas.insumo('harina')).stock_actual, 15000::numeric, 'tras el consumo quedan 15.000 g');

-- ---------- segunda compra, más cara ----------
insert into public.compras_insumos (negocio_id, insumo_id, cantidad_comprada, costo_total)
values (pruebas.id('negocio'), pruebas.id('harina'), 25000, 30000);

select is((pruebas.insumo('harina')).stock_actual, 40000::numeric, 'compra 2: stock 40.000 g');
select is((pruebas.insumo('harina')).costo_promedio, 1.125::numeric,
          'compra 2: promedio ponderado (15.000×1,0 + 30.000) / 40.000 = 1,125');
select is((pruebas.insumo('harina')).costo_reposicion, 1.2::numeric,
          'compra 2: la reposición pasa al precio nuevo (1,2)');
select is((pruebas.insumo('harina')).version, 1,
          'las compras no suben la versión del insumo (sin conflictos falsos)');

-- ---------- stock negativo con aviso ----------
select is((pruebas.consumir('harina', 45000)).stock_negativo, true, 'un consumo mayor al stock se registra con aviso');
select is((pruebas.insumo('harina')).stock_actual, -5000::numeric, 'el stock queda en -5.000 g');
select is((select stock_negativo from public.insumos_costos where id = pruebas.id('harina')), true,
          'la vista marca el stock negativo');

-- Compra con stock negativo: el promedio pasa a ser el costo de la compra
insert into public.compras_insumos (negocio_id, insumo_id, cantidad_comprada, costo_total)
values (pruebas.id('negocio'), pruebas.id('harina'), 10000, 13000);
select is((pruebas.insumo('harina')).stock_actual, 5000::numeric, 'compra 3: stock vuelve a 5.000 g');
select is((pruebas.insumo('harina')).costo_promedio, 1.3::numeric,
          'compra 3 sobre stock negativo: promedio = costo de la compra (1,3)');

-- Compra antigua registrada tarde (sin conexión): entra al promedio, no pisa la reposición
insert into public.compras_insumos (negocio_id, insumo_id, cantidad_comprada, costo_total, comprada_en)
values (pruebas.id('negocio'), pruebas.id('harina'), 1000, 900, now() - interval '10 days');
select is((pruebas.insumo('harina')).costo_promedio, 1.233333::numeric,
          'compra antigua: promedio (5.000×1,3 + 900) / 6.000 = 1,233333');
select is((pruebas.insumo('harina')).costo_reposicion, 1.3::numeric,
          'compra antigua: la reposición sigue siendo la más reciente (1,3)');

-- ---------- actualización manual de mercado ----------
select is((public.actualizar_costo_reposicion(pruebas.id('harina'), 1.5)).costo_reposicion, 1.5::numeric,
          'el proveedor sube el precio: reposición 1,5 sin compra física');
select is((pruebas.insumo('harina')).costo_promedio, 1.233333::numeric,
          'la actualización de mercado no toca el promedio contable');
select is((pruebas.insumo('harina')).stock_actual, 6000::numeric, 'ni el stock');
select is((public.actualizar_costo_reposicion(pruebas.id('harina'), 1.4, now() - interval '5 days')).costo_reposicion,
          1.5::numeric, 'un precio de mercado más antiguo no reemplaza al vigente');

-- ---------- alerta de 30 días ----------
select lives_ok($$ select public.actualizar_costo_reposicion(pruebas.id('aceite'), 3.5, now() - interval '31 days') $$,
                'se registra un precio de mercado de hace 31 días');
select is((select costo_desactualizado from public.insumos_costos where id = pruebas.id('aceite')), true,
          'precio con más de 30 días: alerta de desfase');
select is((select costo_desactualizado from public.insumos_costos where id = pruebas.id('harina')), false,
          'precio reciente: sin alerta');
select is((select sin_costo_reposicion from public.insumos_costos where id = pruebas.id('sin_base')), true,
          'insumo sin costo: se informa aparte');

-- ---------- producción ----------
insert into pruebas.ids values ('pan', gen_random_uuid()), ('prod', gen_random_uuid()),
                               ('mayonesa', gen_random_uuid());
insert into public.platos (id, negocio_id, nombre, precio_venta) values
    (pruebas.id('pan'), pruebas.id('negocio'), 'Pan amasado', 1500),
    (pruebas.id('mayonesa'), pruebas.id('negocio'), 'Mayonesa', 900);
insert into public.plato_insumos (negocio_id, plato_id, insumo_id, cantidad, unidad) values
    (pruebas.id('negocio'), pruebas.id('pan'), pruebas.id('harina'), 0.2, 'kg'),
    (pruebas.id('negocio'), pruebas.id('mayonesa'), pruebas.id('aceite'), 50, 'g');   -- masa ≠ volumen

-- 3 porciones × 0,2 kg × 1000 g/kg × (1 + 10 %) = 660 g; costo 660 × 1,233333 = 813,99978
select is((public.registrar_produccion(pruebas.id('prod'), pruebas.id('pan'), 3)).costo_total,
          813.999780::numeric, 'producción: 660 g de harina al costo promedio (merma 10 %)');
select is((pruebas.insumo('harina')).stock_actual, 5340::numeric, 'la producción descuenta 660 g');
select is((public.registrar_produccion(pruebas.id('prod'), pruebas.id('pan'), 3)).costo_total,
          813.999780::numeric, 'reintentar la misma producción no la aplica dos veces');
select is((pruebas.insumo('harina')).stock_actual, 5340::numeric, 'el stock no cambia con el reintento');
select throws_ok($$ select public.registrar_produccion(gen_random_uuid(), pruebas.id('mayonesa'), 1) $$,
                 '22023', null, 'no se convierte masa en volumen (D4)');

-- ---------- reglas ----------
select throws_ok($$
    insert into public.compras_insumos (negocio_id, insumo_id, cantidad_comprada, costo_total)
    values (pruebas.id('negocio'), pruebas.id('sin_base'), 1000, 500)
$$, '22023', null, 'un insumo sin unidad base confirmada no lleva inventario (D6)');
select throws_ok($$
    update public.insumos set unidad_base = 'ml' where id = pruebas.id('harina')
$$, '42501', null, 'la unidad base no se cambia una vez fijada (D4)');
select throws_ok($$
    update public.compras_insumos set costo_total = 1 where id = pruebas.id('c1')
$$, '42501', null, 'las compras no se editan');
select throws_ok($$
    insert into public.consumos_insumos (negocio_id, insumo_id, cantidad, motivo)
    values (pruebas.id('negocio'), pruebas.id('harina'), 1, 'produccion')
$$, '42501', null, 'los consumos de producción solo vienen de registrar_produccion()');
select throws_ok($$
    insert into public.compras_insumos (negocio_id, insumo_id, cantidad_comprada, costo_total)
    values (pruebas.id('negocio'), pruebas.id('harina'), 0, 100)
$$, '23514', null, 'la cantidad comprada debe ser mayor que cero');

-- ---------- el lector solo consulta ----------
select pruebas.como('00000000-0000-4000-8000-000000000004');
select throws_ok($$
    insert into public.compras_insumos (negocio_id, insumo_id, cantidad_comprada, costo_total)
    values (pruebas.id('negocio'), pruebas.id('harina'), 1000, 1000)
$$, '42501', null, 'el lector no registra compras');
select throws_ok($$ select public.actualizar_costo_reposicion(pruebas.id('harina'), 9) $$,
                 '42501', null, 'el lector no actualiza precios de mercado');
select throws_ok($$ select public.registrar_produccion(gen_random_uuid(), pruebas.id('pan'), 1) $$,
                 '42501', null, 'el lector no registra producciones');

select * from finish();
rollback;
