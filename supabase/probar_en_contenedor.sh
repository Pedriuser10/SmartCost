#!/usr/bin/env bash
# Prueba la migración en un Postgres de Supabase DESECHABLE (Docker), sin tocar ningún
# proyecto Supabase local ni remoto: sin puertos publicados, sin volúmenes con nombre,
# y el contenedor se elimina al terminar.
#   1. aplica la migración          2. ejecuta las pruebas pgTAP
#   3. aplica el DOWN y verifica que no queda nada   4. vuelve a aplicar la migración
# Uso: bash supabase/probar_en_contenedor.sh   (desde la raíz del repositorio)
set -euo pipefail
IMAGEN="${IMAGEN:-public.ecr.aws/supabase/postgres:17.11.0.011}"
NOMBRE="smartcost_pg_prueba_$$"
DIR="$(cd "$(dirname "$0")" && pwd)"
MIGRACION="$DIR/migrations/20261126000000_esquema_inicial.sql"
DOWN="$DIR/rollback/20261126000000_esquema_inicial.down.sql"

docker run -d --rm --name "$NOMBRE" \
    -e POSTGRES_PASSWORD="$(head -c 24 /dev/urandom | base64 | tr -dc A-Za-z0-9)" "$IMAGEN" >/dev/null
trap 'docker stop "$NOMBRE" >/dev/null 2>&1 || true' EXIT

psql_() { docker exec -i "$NOMBRE" psql -U postgres -h localhost -X -q -v ON_ERROR_STOP=1 "$@"; }
for _ in $(seq 1 60); do
    docker exec "$NOMBRE" pg_isready -U postgres -h localhost >/dev/null 2>&1 && break
    sleep 2
done

psql_ < "$MIGRACION" && echo "migración aplicada"
fallos=0
for prueba in "$DIR"/tests/database/*.test.sql; do
    salida="$(docker exec -i "$NOMBRE" psql -U postgres -h localhost -X -q -tA < "$prueba" 2>&1)"
    ok=$(grep -c '^ok ' <<<"$salida" || true)
    plan=$(grep -oE '^1\.\.[0-9]+' <<<"$salida" | cut -d. -f3)
    echo "$(basename "$prueba"): $ok de ${plan:-?}"
    if [ "$ok" != "$plan" ]; then
        fallos=1
        grep -vE '^ok |^$' <<<"$salida" || true
    fi
done
psql_ < "$DOWN" 2>/dev/null
restos=$(psql_ -tAc "select count(*) from pg_tables where schemaname = 'public'")
echo "DOWN aplicado: quedan $restos tablas en public"
[ "$restos" = "0" ] || fallos=1
psql_ < "$MIGRACION" && echo "migración aplicada de nuevo tras el DOWN"
exit $fallos
