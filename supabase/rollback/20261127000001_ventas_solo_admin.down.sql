-- DOWN de 20261127000001_ventas_solo_admin.sql: el editor vuelve a poder registrar ventas.
begin;
drop policy ventas_registrar on public.ventas;
create policy ventas_registrar on public.ventas for insert to authenticated
    with check (privado.puede_editar(negocio_id));
commit;
