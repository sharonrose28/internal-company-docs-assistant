# Docker deployment

Copy `.env.example` to `.env`, replace every placeholder secret, and set `OPENAI_API_KEY`.
Do not commit `.env`.

```sh
docker compose config
docker compose build
docker compose up -d
docker compose ps
```

The API is available at `http://127.0.0.1:8000` and Flower at
`http://127.0.0.1:5555/flower/` by default. Set the bind-address variables to `0.0.0.0`
only when an authenticated TLS reverse proxy or private load balancer protects the services.

PostgreSQL, Redis, and Qdrant are attached only to the internal `backend` network and expose no
host ports. Named volumes preserve database, Redis AOF, Qdrant vectors, uploaded documents, and
Celery Beat state. The `migrate` service runs Alembic once; dependent application services start
only after it succeeds.

For upgrades, pin `IMAGE_TAG` to an immutable release identifier, build/pull that image, then run
`docker compose up -d`. Back up the `postgres`, `qdrant`, and `uploads` volumes before schema or
application upgrades. Run more worker replicas with `docker compose up -d --scale worker=3`; Beat
must remain a singleton to avoid duplicate scheduled tasks.
