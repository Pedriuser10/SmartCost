-- Pruebas del esquema inicial (pgTAP). Todo ocurre dentro de una transacción que se
-- revierte al final: no deja datos. Usuarios ficticios identificados solo por UUID.
begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

select plan(45);

-- ---------- preparación ----------
insert into auth.users (id) values
    ('00000000-0000-4000-8000-000000000001'),  -- propietario
    ('00000000-0000-4000-8000-000000000002'),  -- administrador
    ('00000000-0000-4000-8000-000000000003'),  -- editor
    ('00000000-0000-4000-8000-000000000004'),  -- lector
    ('00000000-0000-4000-8000-000000000005');  -- ajeno al negocio

create schema pruebas;
grant usage on schema pruebas to authenticated, anon;

-- Actuar como un usuario autenticado (igual que una petición con su JWT)
create function pruebas.como(p_usuario uuid) returns void language plpgsql as $$
begin
    perform set_config('request.jwt.claims',
                       json_build_object('sub', p_usuario, 'role', 'authenticated')::text, true);
    -- Formato antiguo, que usa la imagen base de Postgres de Supabase en auth.uid()
    perform set_config('request.jwt.claim.sub', p_usuario::text, true);
    perform set_config('role', 'authenticated', true);
end $$;

-- Cuántas filas tocó una sentencia (RLS filtra en silencio: 0 = no autorizado o no visible)
create function pruebas.filas(p_sql text) returns integer language plpgsql as $$
declare n integer;
begin
    execute p_sql;
    get diagnostics n = row_count;
    return n;
end $$;

create table pruebas.ids (clave text primary key, id uuid);
grant select, insert on pruebas.ids to authenticated;
create function pruebas.id(p text) returns uuid language sql stable as $$
    select id from pruebas.ids where clave = p
$$;

-- ---------- crear negocio y miembros ----------
select pruebas.como('00000000-0000-4000-8000-000000000001');
insert into pruebas.ids values ('negocio', public.crear_negocio('Picada de prueba'));

select is((select rol::text from public.miembros where negocio_id = pruebas.id('negocio')),
          'propietario', 'quien crea el negocio queda como propietario');

select lives_ok($$
    insert into public.miembros (negocio_id, usuario_id, rol) values
        (pruebas.id('negocio'), '00000000-0000-4000-8000-000000000002', 'administrador'),
        (pruebas.id('negocio'), '00000000-0000-4000-8000-000000000003', 'editor')
$$, 'el propietario agrega un administrador y un editor');

select throws_ok($$
    insert into public.miembros (negocio_id, usuario_id, rol)
    values (pruebas.id('negocio'), '00000000-0000-4000-8000-000000000005', 'propietario')
$$, '42501', null, 'nadie agrega otro propietario (solo por transferencia)');

select pruebas.como('00000000-0000-4000-8000-000000000002');
select lives_ok($$
    insert into public.miembros (negocio_id, usuario_id, rol)
    values (pruebas.id('negocio'), '00000000-0000-4000-8000-000000000004', 'lector')
$$, 'el administrador agrega un lector');

select throws_ok($$
    insert into public.miembros (negocio_id, usuario_id, rol)
    values (pruebas.id('negocio'), '00000000-0000-4000-8000-000000000005', 'administrador')
$$, '42501', null, 'el administrador no crea administradores (⏳)');

select is(pruebas.filas($$
    update public.miembros set rol = 'lector'
    where negocio_id = pruebas.id('negocio') and usuario_id = '00000000-0000-4000-8000-000000000003'
$$), 0, 'el administrador no cambia roles (➜ sin confirmar)');

select pruebas.como('00000000-0000-4000-8000-000000000003');
select throws_ok($$
    insert into public.miembros (negocio_id, usuario_id, rol)
    values (pruebas.id('negocio'), '00000000-0000-4000-8000-000000000005', 'lector')
$$, '42501', null, 'el editor no administra miembros');

-- ---------- datos del negocio: editor ----------
select lives_ok($$
    insert into pruebas.ids values ('insumo', gen_random_uuid()), ('plato', gen_random_uuid()),
                                   ('rel', gen_random_uuid()), ('insumo2', gen_random_uuid());
    insert into public.insumos (id, negocio_id, nombre, unidad, precio, merma_pct)
    values (pruebas.id('insumo'), pruebas.id('negocio'), 'Tomate', '10kg', 1200, 5),
           (pruebas.id('insumo2'), pruebas.id('negocio'), 'Sal', 'kg', 800, 0);
    insert into public.platos (id, negocio_id, nombre, precio_venta, mano_obra)
    values (pruebas.id('plato'), pruebas.id('negocio'), 'Ensalada', 4500, 500);
    insert into public.plato_insumos (id, negocio_id, plato_id, insumo_id, cantidad)
    values (pruebas.id('rel'), pruebas.id('negocio'), pruebas.id('plato'), pruebas.id('insumo'), 0.25);
$$, 'el editor crea insumos, platos e ingredientes con UUID del cliente');

select is((select version from public.insumos where id = pruebas.id('insumo')), 1,
          'el registro nuevo empieza en la versión 1');
select throws_ok($$
    update public.insumos set version = 99 where id = pruebas.id('insumo')
$$, '42501', null, 'el cliente no puede escribir la versión');
select throws_ok($$
    update public.insumos set stock_actual = 1000 where id = pruebas.id('insumo')
$$, '42501', null, 'el cliente no puede escribir el stock');
select is((select created_by from public.insumos where id = pruebas.id('insumo')),
          '00000000-0000-4000-8000-000000000003'::uuid, 'el servidor registra quién creó el registro');
select is((select unidad from public.insumos where id = pruebas.id('insumo')), '10kg',
          'la unidad se guarda tal como se ingresó (D4)');

select is(pruebas.filas($$
    update public.insumos set precio = 1300 where id = pruebas.id('insumo')
$$), 1, 'el editor actualiza el precio de compra (D1.1)');
select is((select version from public.insumos where id = pruebas.id('insumo')), 2,
          'cada cambio sube la versión en uno');
select ok((select sync_seq from public.insumos where id = pruebas.id('insumo'))
          > (select sync_seq from public.plato_insumos where id = pruebas.id('rel')),
          'sync_seq crece con cada escritura (descarga incremental)');

-- Conflicto: el cliente edita pensando que la versión sigue siendo 1
select is(pruebas.filas($$
    update public.insumos set precio = 1400
    where id = pruebas.id('insumo') and version = 1
$$), 0, 'una edición sobre una versión vieja no se aplica (conflicto detectable)');
select is((select precio from public.insumos where id = pruebas.id('insumo')), 1300::numeric,
          'el conflicto no sobrescribe el valor del servidor');

select throws_ok($$
    insert into public.insumos (id, negocio_id, nombre) values (pruebas.id('insumo'), pruebas.id('negocio'), 'Tomate')
$$, '23505', null, 'reenviar la misma creación no la duplica (idempotencia por UUID)');

select throws_ok($$
    update public.insumos set deleted_at = now() where id = pruebas.id('insumo2')
$$, '42501', null, 'el editor no elimina insumos (⏳)');

select is(pruebas.filas($$
    update public.plato_insumos set deleted_at = now() where id = pruebas.id('rel')
$$), 1, 'el editor quita un ingrediente de una receta');

select throws_ok($$
    update public.plato_insumos set deleted_at = null where id = pruebas.id('rel')
$$, '42501', null, 'un registro eliminado no se restaura (⏳)');

select throws_ok($$
    insert into public.insumos (negocio_id, nombre, precio) values (pruebas.id('negocio'), 'Malo', -1)
$$, '23514', null, 'no se aceptan precios negativos');

select throws_ok($$
    delete from public.insumos where id = pruebas.id('insumo2')
$$, '42501', null, 'nadie borra filas físicamente');

-- ---------- lector ----------
select pruebas.como('00000000-0000-4000-8000-000000000004');
select is((select count(*)::int from public.insumos), 2, 'el lector ve los insumos');
select is((select count(*)::int from public.miembros), 1, 'el lector solo ve su propia membresía (⏳)');
select throws_ok($$
    insert into public.insumos (negocio_id, nombre) values (pruebas.id('negocio'), 'Intruso')
$$, '42501', null, 'el lector no crea insumos');
select is(pruebas.filas($$
    update public.insumos set precio = 1 where negocio_id = pruebas.id('negocio')
$$), 0, 'el lector no modifica insumos');

-- ---------- administrador: borrado lógico en cascada ----------
select pruebas.como('00000000-0000-4000-8000-000000000002');
select is((select count(*)::int from public.miembros), 4, 'el administrador ve todos los miembros');
select lives_ok($$
    insert into pruebas.ids values ('rel2', gen_random_uuid());
    insert into public.plato_insumos (id, negocio_id, plato_id, insumo_id, cantidad)
    values (pruebas.id('rel2'), pruebas.id('negocio'), pruebas.id('plato'), pruebas.id('insumo2'), 0.01)
$$, 'el administrador agrega un ingrediente');
select is(pruebas.filas($$
    update public.insumos set deleted_at = now() where id = pruebas.id('insumo2')
$$), 1, 'el administrador elimina un insumo (borrado lógico)');
select isnt((select deleted_at from public.plato_insumos where id = pruebas.id('rel2')), null,
            'al eliminar el insumo sale también de las recetas (cascada lógica)');
select throws_ok($$
    update public.insumos set nombre = 'Sal de mar' where id = pruebas.id('insumo2')
$$, '42501', null, 'un insumo eliminado no se edita');
select throws_ok($$
    insert into public.plato_insumos (negocio_id, plato_id, insumo_id, cantidad)
    values (pruebas.id('negocio'), pruebas.id('plato'), pruebas.id('insumo2'), 1)
$$, '23503', null, 'no se agrega a una receta un insumo eliminado');
select is(pruebas.filas($$
    update public.negocios set nombre = 'Otro nombre' where id = pruebas.id('negocio')
$$), 0, 'el administrador no edita nombre ni moneda del negocio (⏳)');

-- ---------- propietario ----------
select pruebas.como('00000000-0000-4000-8000-000000000001');
select is(pruebas.filas($$
    update public.negocios set nombre = 'Picada renovada' where id = pruebas.id('negocio')
$$), 1, 'el propietario edita el nombre del negocio');
select throws_ok($$
    update public.negocios set deleted_at = now() where id = pruebas.id('negocio')
$$, '42501', null, 'archivar el negocio aún no está permitido (⏳)');
select throws_ok($$
    update public.miembros set rol = 'propietario'
    where negocio_id = pruebas.id('negocio') and usuario_id = '00000000-0000-4000-8000-000000000002'
$$, '42501', null, 'no se asciende a propietario fuera de la transferencia');
select throws_ok($$
    delete from public.miembros
    where negocio_id = pruebas.id('negocio') and usuario_id = '00000000-0000-4000-8000-000000000001'
$$, '42501', null, 'el único propietario no puede salir');
select throws_ok($$
    update public.miembros set rol = 'administrador'
    where negocio_id = pruebas.id('negocio') and usuario_id = '00000000-0000-4000-8000-000000000001'
$$, '42501', null, 'el único propietario no puede bajarse el rol');

-- ---------- aislamiento entre negocios ----------
select pruebas.como('00000000-0000-4000-8000-000000000005');
select is((select count(*)::int from public.insumos), 0, 'alguien ajeno no ve los insumos del negocio');
select throws_ok($$
    insert into public.insumos (negocio_id, nombre) values (pruebas.id('negocio'), 'Intruso')
$$, '42501', null, 'alguien ajeno no escribe en el negocio');
select throws_ok($$
    insert into pruebas.ids values ('negocio_b', public.crear_negocio('Otro local'));
    insert into pruebas.ids values ('insumo_b', gen_random_uuid());
    insert into public.insumos (id, negocio_id, nombre) values (pruebas.id('insumo_b'), pruebas.id('negocio_b'), 'Ajeno');
    insert into public.plato_insumos (negocio_id, plato_id, insumo_id, cantidad)
    values (pruebas.id('negocio_b'), pruebas.id('plato'), pruebas.id('insumo_b'), 1)
$$, '23503', null, 'una receta no puede usar un plato de otro negocio');

-- ---------- sin sesión ----------
reset role;
select set_config('request.jwt.claims', '', true);
select set_config('request.jwt.claim.sub', '', true);
set local role anon;
select throws_ok($$ select count(*) from public.insumos $$, '42501', null,
                 'sin sesión (anon) no se lee nada');
select throws_ok($$ select public.crear_negocio('Anónimo') $$, '42501', null,
                 'sin sesión no se crean negocios');

select * from finish();
rollback;
