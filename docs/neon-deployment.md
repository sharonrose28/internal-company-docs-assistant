# Neon PostgreSQL deployment

Neon replaces only the PostgreSQL container. FastAPI, Celery, Redis, Qdrant and the frontend continue to run on the VPS.

## Create Neon database

1. Create a Neon project in the region closest to the VPS.
2. Open **Connect** in the Neon console.
3. Copy the direct connection string for Alembic-compatible migrations. A pooled URL can be evaluated later for application traffic.
4. Never paste the connection string into source control, chat, or deployment logs.

The application converts `postgresql://` to SQLAlchemy's `postgresql+asyncpg://`, converts `sslmode=require` to asyncpg's `ssl=require`, and removes the libpq-only `channel_binding` parameter. TLS remains required.

## Configure VPS

In the server-side `.env` file only:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require&channel_binding=require
```

Restrict the file:

```bash
chmod 600 .env
```

## Deploy without local PostgreSQL

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.vps.yml \
  -f docker-compose.neon.yml \
  config --quiet

docker compose \
  -f docker-compose.yml \
  -f docker-compose.vps.yml \
  -f docker-compose.neon.yml \
  up --build -d
```

The `postgres` service is placed behind the inactive `local-postgres` profile. The one-shot `migrate` service applies Alembic migrations to Neon before the API starts.

## Verify

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.vps.yml \
  -f docker-compose.neon.yml \
  logs --since=10m migrate api worker

curl -fsS http://127.0.0.1/health
```

Use Neon monitoring to observe compute activation, active connections, storage and transfer. The free plan can scale to zero, so the first request after inactivity may be slower.
