-- =============================================================================
-- SmartCost: solo el propietario y el administrador registran ventas
--
-- Decisión del autor (2026-11-27): registrar ventas queda limitado a `propietario` y
-- `administrador`. Antes estaba habilitado también para `editor`, por analogía con los
-- consumos, y marcado como pendiente de confirmar (➜). El editor sigue registrando
-- compras, consumos y producciones; el lector solo consulta.
--
-- Reversión: supabase/rollback/20261127000001_ventas_solo_admin.down.sql
-- =============================================================================

drop policy ventas_registrar on public.ventas;
create policy ventas_registrar on public.ventas for insert to authenticated
    with check (coalesce(privado.rol_en(negocio_id)::text, '') in ('propietario', 'administrador'));
