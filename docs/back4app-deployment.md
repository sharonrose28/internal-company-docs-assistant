# Back4App free-container deployment

Back4App runs the English React frontend, FastAPI API, and one Celery worker
from the repository's root `Dockerfile`. PostgreSQL, Redis/Valkey, and Qdrant
remain managed external services.

## Create the application

1. Sign in to Back4App and choose **Containers** > **Create a new app**.
2. Connect `sharonrose28/internal-company-docs-assistant`.
3. Select branch `main`, root directory `/`, and the Free container.
4. Keep the Dockerfile path as `Dockerfile` and deploy.

## Environment variables

Add these in the container's Environment settings. Store credentials as
secrets and never commit them to Git:

```text
ENVIRONMENT=production
DATABASE_URL=<Aiven or Neon PostgreSQL service URI>
REDIS_URL=<Aiven Valkey or Upstash Redis URI>
CACHE_REDIS_URL=<same Redis URI>
QDRANT_URL=<Qdrant Cloud HTTPS cluster URL>
QDRANT_API_KEY=<Qdrant Cloud API key>
OPENAI_API_KEY=<OpenAI API key>
JWT_SECRET=<random value containing at least 32 characters>
CORS_ORIGINS=https://<assigned-app-name>.b4a.run
CELERY_CONCURRENCY=1
UPLOAD_DIR=/data/uploads
```

Do not define `VITE_API_URL`: the frontend and API use the same public origin.
Back4App injects `PORT`; the application reads it automatically.

## Verify

- Open `https://<assigned-app-name>.b4a.run/health`.
- Open `https://<assigned-app-name>.b4a.run/signup`.
- Create an employee account and sign in.

## Free-tier limits

The free container provides only 256 MB RAM and is appropriate for a demo,
not production. PDF extraction or hybrid retrieval may exceed that limit.
Uploaded source files are ephemeral; PostgreSQL metadata and Qdrant vectors
remain durable in their external services.
