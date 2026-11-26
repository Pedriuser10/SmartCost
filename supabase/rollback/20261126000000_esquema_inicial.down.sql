-- DOWN de 20261126000000_esquema_inicial.sql
-- La CLI de Supabase solo aplica migraciones hacia adelante: este archivo se ejecuta a
-- mano y SOLO en un entorno de desarrollo. BORRA TODAS LAS TABLAS Y SUS DATOS.
-- No ejecutar en producción sin respaldo y autorización explícita.
begin;
drop view if exists public.insumos_costos;
drop function if exists public.registrar_produccion(uuid, uuid, numeric, timestamptz);
drop function if exists public.actualizar_costo_reposicion(uuid, numeric, timestamptz);
drop function if exists public.crear_negocio(text, text);
-- Antes que las tablas: sus funciones usan los tipos de fila de las tablas
drop schema if exists privado cascade;   -- funciones auxiliares y de trigger (y sus triggers)
drop table if exists public.consumos_insumos, public.producciones, public.compras_insumos,
    public.plato_insumos, public.platos, public.insumos, public.miembros, public.negocios,
    public.unidades;
drop sequence if exists public.sync_seq;
drop type if exists public.rol_negocio;
commit;
