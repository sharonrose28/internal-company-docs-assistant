# No-card demo deployment on Render

This is a demonstration topology, not a production deployment. Render Free web services sleep after 15 minutes of inactivity and have ephemeral filesystems. A restart during ingestion can lose the uploaded source file.

## Managed dependencies

Create these accounts and resources without entering credentials into source control:

1. **Neon Free**: PostgreSQL. Copy a direct connection URL.
2. **Upstash Redis Free**: Celery broker/cache. Copy the TLS Redis URL. For Celery, append `?ssl_cert_reqs=required` if the URL has no query string.
3. **Qdrant Cloud Free**: create a free cluster and API key. Copy its HTTPS cluster URL.
4. **Render Free**: connect the GitHub repository and create a Blueprint from `render.yaml`.

Qdrant Free and Upstash Free do not require a credit card. Never place their credentials, the Neon password, or the OpenAI key in Git.

## Render Blueprint secrets

During the initial Blueprint creation, Render prompts for variables marked `sync: false`.

Backend:

```text
DATABASE_URL=<Neon direct connection URL>
REDIS_URL=<Upstash rediss URL with ssl_cert_reqs=required>
CACHE_REDIS_URL=<same Upstash rediss URL>
QDRANT_URL=<Qdrant HTTPS cluster URL>
QDRANT_API_KEY=<Qdrant API key>
OPENAI_API_KEY=<OpenAI API key>
CORS_ORIGINS=https://company-docs-web.onrender.com
```

Frontend:

```text
VITE_API_URL=https://company-docs-api.onrender.com
```

Use the actual Render-generated service URLs if the names receive suffixes. Redeploy both services after correcting the URLs.

## Runtime model

The free tier does not support a free Render background-worker service. `app.run_railway` therefore runs FastAPI and one Celery worker in the same web container. Upstash provides the external Redis protocol endpoint; Neon and Qdrant preserve database/vector state.

## Verify

1. Open `https://<api-service>.onrender.com/health` and expect `{"status":"healthy"}`.
2. Open the static frontend URL.
3. Create the first administrator from a temporary local command connected to Neon, or upgrade to a Render plan with shell access. Do not place its password in a build/start command.
4. Upload a small document while the service is awake and wait for it to reach `ready`.

## Limitations

- First request after sleep can take about one minute.
- Uploaded files are not durable; only extracted PostgreSQL chunks and Qdrant vectors persist.
- A sleeping web service cannot process queued Celery work.
- Free Qdrant clusters suspend after inactivity and can be deleted after prolonged inactivity.
- Free Upstash databases can be archived after inactivity.
- There is no SLA, horizontal scaling, durable upload storage, or guaranteed background processing.
