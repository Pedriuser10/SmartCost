-- Pruebas de venta directa, precio sugerido y protección del margen (pgTAP). Se revierte todo.
--
-- Caso pedido: una caja de 24 unidades a un precio, una venta parcial y una segunda caja
-- más cara antes de agotar la primera. Margen objetivo 30 % (sobre el precio), IVA 19 %,
-- costos netos, precio con IVA redondeado hacia arriba a $10:
--
--   caja 1   24 u por $12.000 neto     → costo 500 · sugerido 500 × 1,19 / 0,70 = $850
--   aprobar  precio de góndola $850    → margen real 30 %
--   venta    10 u a $850               → total $8.500 · neto 7.142,857143 · costo 5.000 (promedio 500)
--   caja 2   24 u por $14.400 neto     → promedio (14×500 + 14.400) / 38 = 563,157895
--                                          reposición 600 · sugerido 600 × 1,19 / 0,70 = $1.020
--            el precio de góndola sigue en $850 → margen real 16 % < 30 % → "margen bajo"
begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

select plan(42);

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
create function pruebas.p(p text) returns public.insumos_costos language sql stable as $$
    select * from public.insumos_costos where id = pruebas.id(p)
$$;
create function pruebas.vender(p text, p_cantidad numeric, p_precio numeric default null)
returns public.ventas language plpgsql as $$
declare r public.ventas;
begin
    insert into public.ventas (negocio_id, insumo_id, cantidad, precio_unitario)
    values (pruebas.id('negocio'), pruebas.id(p), p_cantidad, p_precio) returning * into r;
    return r;
end $$;
create function pruebas.comprar(p text, p_cantidad numeric, p_total numeric, p_en timestamptz default now())
returns void language sql as $$
    insert into public.compras_insumos (negocio_id, insumo_id, cantidad_comprada, costo_total, comprada_en)
    values (pruebas.id('negocio'), pruebas.id(p), p_cantidad, p_total, p_en)
$$;

select pruebas.como('00000000-0000-4000-8000-000000000001');
insert into pruebas.ids values ('negocio', public.crear_negocio('Almacén de prueba'));
insert into public.miembros (negocio_id, usuario_id, rol) values
    (pruebas.id('negocio'), '00000000-0000-4000-8000-000000000003', 'editor'),
    (pruebas.id('negocio'), '00000000-0000-4000-8000-000000000004', 'lector');

select is((select tasa_iva from public.negocios where id = pruebas.id('negocio')), 0.19::numeric,
          'IVA del negocio: 19 % por defecto');
select is((select dias_alerta_precio from public.negocios where id = pruebas.id('negocio')), 30,
          'umbral de la alerta de precio: 30 días por defecto');

-- ---------- el editor crea productos y registra compras ----------
select pruebas.como('00000000-0000-4000-8000-000000000003');
insert into pruebas.ids values ('jugo', gen_random_uuid()), ('cable', gen_random_uuid()),
                               ('harina', gen_random_uuid()), ('sinprecio', gen_random_uuid());
insert into public.insumos (id, negocio_id, nombre, unidad, unidad_base, se_vende, margen_objetivo) values
    (pruebas.id('jugo'),      pruebas.id('negocio'), 'Jugo en caja',  'caja 24', 'unidad', true,  30),
    (pruebas.id('cable'),     pruebas.id('negocio'), 'Cable 2,5 mm',  'rollo',   'm',      true,  40),
    (pruebas.id('harina'),    pruebas.id('negocio'), 'Harina',        '25kg',    'g',      false, null),
    (pruebas.id('sinprecio'), pruebas.id('negocio'), 'Fósforos',      'paquete', 'unidad', true,  null);

select pruebas.comprar('jugo', 24, 12000);
select is((pruebas.p('jugo')).costo_reposicion, 500::numeric, 'caja 1: costo unitario 500 neto');
select is((pruebas.p('jugo')).precio_sugerido, 850::numeric,
          'precio sugerido = 500 × 1,19 / 0,70 = $850 (sin residuo que lo suba a $860)');
select is((pruebas.p('jugo')).precio_venta, null::numeric, 'la compra no fija el precio de góndola');
select is((pruebas.p('jugo')).sin_precio_venta, true, 'la vista avisa que falta aprobar el precio');

select throws_ok($$ select public.fijar_precio_venta(pruebas.id('jugo')) $$, '42501', null,
                 'el editor no aprueba precios');
select throws_ok($$ select pruebas.vender('jugo', 1) $$, '22023', null,
                 'no se vende un producto sin precio aprobado');

-- ---------- el propietario aprueba el sugerido ----------
select pruebas.como('00000000-0000-4000-8000-000000000001');
select is((public.fijar_precio_venta(pruebas.id('jugo'))).precio_venta, 850::numeric,
          'el propietario aprueba el precio sugerido: $850');
select is((pruebas.p('jugo')).margen_real, 30::numeric, 'margen real 30 %');
select is((pruebas.p('jugo')).margen_bajo, false, 'sin alerta de margen');
select isnt((pruebas.p('jugo')).precio_actualizado_en, null, 'se registra cuándo se aprobó el precio');

-- ---------- venta parcial ----------
select pruebas.como('00000000-0000-4000-8000-000000000003');
insert into pruebas.ids values ('venta1', gen_random_uuid());
select lives_ok($$
    insert into public.ventas (id, negocio_id, insumo_id, cantidad)
    values (pruebas.id('venta1'), pruebas.id('negocio'), pruebas.id('jugo'), 10)
$$, 'el editor registra una venta de 10 unidades');
select is((select total from public.ventas where id = pruebas.id('venta1')), 8500::numeric,
          'venta: total $8.500 al precio de góndola');
select is((select ingreso_neto from public.ventas where id = pruebas.id('venta1')), 7142.857143::numeric,
          'ingreso neto = 8.500 / 1,19');
select is((select costo_venta from public.ventas where id = pruebas.id('venta1')), 5000::numeric,
          'costo de venta al costo promedio (10 × 500)');
select is((select utilidad from public.ventas where id = pruebas.id('venta1')), 2142.857143::numeric,
          'utilidad = ingreso neto − costo de venta');
select is((pruebas.p('jugo')).stock_actual, 14::numeric, 'quedan 14 unidades');
select throws_ok($$
    insert into public.ventas (id, negocio_id, insumo_id, cantidad)
    values (pruebas.id('venta1'), pruebas.id('negocio'), pruebas.id('jugo'), 10)
$$, '23505', null, 'reenviar la misma venta no la duplica (idempotencia)');

-- ---------- segunda caja, más cara ----------
select pruebas.comprar('jugo', 24, 14400);
select is((pruebas.p('jugo')).costo_promedio, 563.157895::numeric,
          'promedio (14×500 + 14.400) / 38 = 563,157895');
select is((pruebas.p('jugo')).costo_reposicion, 600::numeric, 'reposición: 600');
select is((pruebas.p('jugo')).precio_sugerido, 1020::numeric, 'sugerido nuevo: 600 × 1,19 / 0,70 = $1.020');
select is((pruebas.p('jugo')).precio_venta, 850::numeric, 'el precio de góndola NO sube solo');
select is((pruebas.p('jugo')).margen_real, 16::numeric, 'margen real con $850 y costo 600: 16 %');
select is((pruebas.p('jugo')).margen_bajo, true, 'alerta: el margen cayó bajo el objetivo');

select pruebas.como('00000000-0000-4000-8000-000000000001');
select is((public.fijar_precio_venta(pruebas.id('jugo'))).precio_venta, 1020::numeric,
          'el propietario aprueba el alza a $1.020');
select is((pruebas.p('jugo')).margen_bajo, false, 'margen recuperado');

select pruebas.como('00000000-0000-4000-8000-000000000003');
select is((pruebas.vender('jugo', 5)).costo_venta, 2815.789475::numeric,
          'la venta siguiente se costea al promedio (5 × 563,157895)');
select is((pruebas.vender('jugo', 1, 900)).total, 900::numeric,
          'se puede cobrar otro precio (descuento en caja)');

-- ---------- lista de precios del proveedor, sin compra ----------
select lives_ok($$ select public.actualizar_costo_reposicion(pruebas.id('jugo'), 650) $$,
                'el proveedor sube su lista a 650');
select is((pruebas.p('jugo')).precio_sugerido, 1110::numeric, 'sugerido: 650 × 1,19 / 0,70 = 1.105 → $1.110');
select is((pruebas.p('jugo')).stock_actual, 32::numeric, 'la lista no toca el stock');
select is((pruebas.p('jugo')).costo_promedio, 563.157895::numeric, 'ni el costo promedio');
select is((pruebas.p('jugo')).margen_bajo, true, 'con $1.020 y costo 650 el margen vuelve a caer');

-- ---------- reglas ----------
select throws_ok($$ select pruebas.vender('harina', 1, 100) $$, '22023', null,
                 'un insumo que no está a la venta no se vende');
select is((pruebas.vender('jugo', 40)).stock_negativo, true, 'vender más que el stock: se registra con aviso');
select pruebas.comprar('cable', 100, 50000);
select is((pruebas.p('cable')).precio_sugerido, 1000::numeric,
          'unidad de longitud: 500 por metro × 1,19 / 0,60 = 991,67 → $1.000');

select pruebas.como('00000000-0000-4000-8000-000000000004');
select throws_ok($$ select pruebas.vender('jugo', 1) $$, '42501', null, 'el lector no registra ventas');

-- ---------- ajustes del negocio ----------
select pruebas.como('00000000-0000-4000-8000-000000000001');
select pruebas.comprar('cable', 1, 500, now() - interval '10 days');
update public.negocios set dias_alerta_precio = 30 where id = pruebas.id('negocio');
select lives_ok($$ select public.actualizar_costo_reposicion(pruebas.id('harina'), 1.2, now() - interval '10 days') $$,
                'precio de mercado de hace 10 días');
select is((pruebas.p('harina')).costo_desactualizado, false, 'con 30 días de umbral no hay alerta');
update public.negocios set dias_alerta_precio = 7 where id = pruebas.id('negocio');
select is((pruebas.p('harina')).costo_desactualizado, true, 'con umbral de 7 días sí hay alerta');
update public.negocios set tasa_iva = 0 where id = pruebas.id('negocio');
select is((pruebas.p('jugo')).precio_sugerido, 930::numeric,
          'si cambia el IVA, el sugerido se recalcula: 650 / 0,70 = 928,57 → $930');

select * from finish();
rollback;
