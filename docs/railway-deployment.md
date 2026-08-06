# Railway deployment

This deployment maps the Compose application to Railway services. Railway does not run Compose as one unit; each dependency is a service connected through private networking.

## Production topology

```text
Public frontend (Caddy + React)
        |
        | HTTPS
        v
Public backend (FastAPI + Celery worker, shared upload volume)
        |-- private PostgreSQL
        |-- private Redis
        |-- private Qdrant + volume
        +-- OpenAI API
```

The API and Celery worker intentionally run in the same Railway service because Railway volumes attach to one service and the current ingestion implementation uses local files. Attach one volume at `/data/uploads`. For independent API/worker scaling, replace local upload storage with a Railway Bucket or another S3-compatible store first.

## Prerequisites

1. Push this repository to GitHub.
2. Create an empty Railway project and production environment.
3. Keep every service in the same Railway region to minimize private-network latency.

## 1. Add PostgreSQL and Redis

On the Railway project canvas, select **Create -> Database -> PostgreSQL**, then add Redis the same way. Keep both private; neither needs a generated public domain.

## 2. Add Qdrant

Create an empty service using Docker image:

```text
qdrant/qdrant:v1.12.6
```

Name it `Qdrant`, attach a volume mounted at `/qdrant/storage`, and do not generate a public domain. Qdrant listens on port `6333` over Railway private networking.

## 3. Deploy the backend

Create a service named `Backend` from the GitHub repository.

- Root directory: `/`
- Config file path: `/railway.json`
- Volume mount: `/data/uploads`
- Generate a public domain after the first successful deployment.
- Because Railway mounts volumes as root while the image normally uses an unprivileged user, set `RAILWAY_RUN_UID=0` for this volume-backed service. The application still restricts upload paths and filenames.

Add these backend variables. Railway reference syntax uses the actual service names, so change `Postgres`, `Redis`, or `Qdrant` if you named them differently.

```text
ENVIRONMENT=production
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
CACHE_REDIS_URL=${{Redis.REDIS_URL}}
QDRANT_URL=http://${{Qdrant.RAILWAY_PRIVATE_DOMAIN}}:6333
QDRANT_COLLECTION=company_documents_hybrid_v1
UPLOAD_DIR=/data/uploads
OPENAI_API_KEY=<secret>
JWT_SECRET=<at-least-32-random-characters>
JWT_ISSUER=company-docs
JWT_AUDIENCE=company-docs-api
ACCESS_TOKEN_MINUTES=15
CACHE_TTL_SECONDS=900
CELERY_CONCURRENCY=2
CORS_ORIGINS=https://<frontend-domain>
```

Retain the embedding, chunking, retrieval and RAG defaults from `.env.example`, or add explicit production values. `DATABASE_URL` is normalized to SQLAlchemy's asyncpg driver automatically.

The backend config performs `alembic upgrade head` as a Railway pre-deploy command, starts FastAPI and Celery together, binds FastAPI to Railway's injected `PORT`, exposes `/health`, and restarts on failures.

Generate secure values locally without committing them:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 4. Deploy the frontend

Create another service named `Frontend` from the same GitHub repository.

- Root directory: `/frontend`
- Config file path: `/frontend/railway.json`
- Generate a public domain.
- Add `VITE_API_URL=https://<backend-domain>`.

`VITE_API_URL` is compiled into the Vite bundle, so redeploy the frontend whenever it changes. Caddy listens on Railway's `PORT`, serves compressed static assets, answers `/health`, and falls back to `index.html` for React Router routes.

After the frontend domain exists, update `Backend.CORS_ORIGINS` to its exact HTTPS origin with no path, then redeploy the backend. Multiple origins are comma-separated.

## 5. Create the first administrator

Open a Railway shell for the Backend service and run:

```text
python -m app.cli.create_user --email admin@example.com --role admin
```

Enter the password at the prompt. Do not seed administrator passwords in source code or deployment logs.

## 6. Verify

1. `https://<backend-domain>/health` returns `{"status":"healthy"}`.
2. `https://<frontend-domain>/health` returns HTTP 200.
3. Login succeeds from the frontend.
4. Upload a small native-text PDF.
5. Backend logs show the Celery task and the document reaches `ready`.
6. Ask a question and verify citations are returned.

## Optional services

Flower can be added as a separate service from the root Dockerfile with start command:

```text
celery -A app.workers.celery_app:celery_app flower --port=$PORT
```

Give it `REDIS_URL`, generate a domain, and protect it with `FLOWER_BASIC_AUTH`. Do not expose Qdrant, Redis, or PostgreSQL publicly.

Celery Beat is unnecessary unless scheduled tasks are configured. If enabled later, run exactly one Beat replica to prevent duplicate scheduling.

## Operational notes

- Scale the combined Backend vertically, not horizontally: multiple replicas would receive different local upload volumes. Move uploads to a Railway Bucket before horizontal scaling or separating workers.
- Enable backups for PostgreSQL and the Qdrant volume.
- Use Railway environments for staging and production.
- Rotate JWT, OpenAI, database and Redis secrets through Railway Variables.
- Review deployment logs for migration, health-check, worker connection, and Qdrant compatibility errors.
- Never expose `/metrics` publicly without network or authentication controls in a sensitive production environment.
