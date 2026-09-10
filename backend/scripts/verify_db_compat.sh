#!/usr/bin/env bash
# Verifica que a imagem de produção sobe corretamente (migrations + boot + /health) e que o
# ORM faz o round-trip de Enum/Boolean corretamente tanto em MySQL quanto em PostgreSQL.
# Rode isto antes de qualquer deploy que mude models/migrations.
#
# Uso: ./scripts/verify_db_compat.sh   (a partir de backend/)
set -euo pipefail
cd "$(dirname "$0")/.."

NETWORK=estacionamento-compat-check
IMAGE=estacionamento-backend:compat-check

cleanup() {
  docker rm -f compat-mysql compat-postgres compat-redis compat-backend >/dev/null 2>&1 || true
  docker network rm "$NETWORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup
docker network create "$NETWORK" >/dev/null
docker build -q -t "$IMAGE" . >/dev/null

echo "==> Subindo MySQL, PostgreSQL e Redis..."
docker run -d --rm --name compat-mysql --network "$NETWORK" \
  -e MYSQL_ROOT_PASSWORD=rootpass -e MYSQL_DATABASE=estacionamento \
  -e MYSQL_USER=dom_user -e MYSQL_PASSWORD=dom_pass mysql:8.0 >/dev/null
docker run -d --rm --name compat-postgres --network "$NETWORK" \
  -e POSTGRES_USER=dom_user -e POSTGRES_PASSWORD=dom_pass -e POSTGRES_DB=estacionamento \
  postgres:15-alpine >/dev/null
docker run -d --rm --name compat-redis --network "$NETWORK" redis:7-alpine >/dev/null

echo "==> Aguardando MySQL..."
for _ in $(seq 1 40); do
  docker exec compat-mysql mysqladmin ping -uroot -prootpass --silent >/dev/null 2>&1 && break
  sleep 1
done
# MySQL 8 reinicia o processo internamente logo após o primeiro "ping" bem-sucedido —
# espera extra para não conectar durante essa janela de reinício.
sleep 8
for _ in $(seq 1 40); do
  docker exec compat-mysql mysqladmin ping -uroot -prootpass --silent >/dev/null 2>&1 && break
  sleep 1
done

echo "==> Aguardando PostgreSQL..."
for _ in $(seq 1 30); do
  docker exec compat-postgres pg_isready -U dom_user >/dev/null 2>&1 && break
  sleep 1
done

run_check() {
  local nome="$1" url="$2"
  echo "==> Verificando $nome (migrations + round-trip Enum/Boolean)..."
  docker run --rm --network "$NETWORK" \
    -e DATABASE_URL="$url" -e REDIS_URL="redis://compat-redis:6379" \
    -e AUTH0_DOMAIN=fake.auth0.com -e AUTH0_AUDIENCE=x \
    "$IMAGE" sh -c "alembic upgrade head && python -m scripts.verificar_compat_orm"
  echo "OK: $nome"
}

run_check "MySQL"      "mysql+aiomysql://dom_user:dom_pass@compat-mysql:3306/estacionamento"
run_check "PostgreSQL" "postgresql://dom_user:dom_pass@compat-postgres:5432/estacionamento"

echo "==> Compatibilidade MySQL <-> PostgreSQL confirmada."
