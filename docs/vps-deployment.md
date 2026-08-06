# VPS deployment

This guide deploys the complete application to one Ubuntu or Debian VPS with Docker Compose. It is suitable for an educational environment without an uptime SLA. Keep independent backups: the provider may suspend the service and permanently remove data.

## Server requirements

- Ubuntu 22.04/24.04 or Debian 12
- root or sudo SSH access
- public IPv4 address
- ports 22, 80 and optionally 443 allowed by the provider firewall
- at least 4 GB RAM; 2-4 GB swap is recommended during image builds
- at least 25 GB free disk space

## Security preparation

1. Add an SSH public key and confirm key login works.
2. Disable SSH password authentication only after confirming key access.
3. Allow SSH, HTTP and HTTPS through the firewall.
4. Never copy `.env` into Git or send it through chat.
5. Use unique production database, JWT and Flower passwords.

## Install Docker

Follow Docker's official repository instructions for the selected distribution, then verify:

```bash
docker version
docker compose version
```

## Copy and configure the application

Clone the private repository using a deploy key, or copy a release archive that excludes `.env`, `.git`, `.venv`, `node_modules`, test output and local data.

```bash
cd /opt
git clone <repository-url> company-docs
cd company-docs
cp .env.example .env
chmod 600 .env
```

Edit `.env` on the server. Required values include `POSTGRES_PASSWORD`, `JWT_SECRET`, and `OPENAI_API_KEY`. Set `CELERY_CONCURRENCY=1` on a 4 GB VPS. The OpenAI key must exist only in the server-side `.env` file.

For plain HTTP by IP, keep:

```text
APP_ADDRESS=:80
```

For a domain whose A/AAAA record points to the VPS, set:

```text
APP_ADDRESS=docs.example.com
```

Caddy will obtain and renew TLS certificates automatically when ports 80 and 443 are reachable. Add `443:443` and `443:443/udp` to the frontend ports in the VPS override when enabling a domain.

## Start the stack

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml config
docker compose -f docker-compose.yml -f docker-compose.vps.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.vps.yml ps
```

The public Caddy container serves React and forwards `/api/*` to FastAPI over the private Docker network. PostgreSQL, Redis and Qdrant are not exposed publicly. Flower and Beat are disabled by default through Compose profiles.

## Create the administrator

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml exec api \
  python -m app.cli.create_user --email admin@example.com --role admin
```

## Verify and operate

```bash
curl -fsS http://127.0.0.1/health
docker compose -f docker-compose.yml -f docker-compose.vps.yml logs --since=10m api worker
docker compose -f docker-compose.yml -f docker-compose.vps.yml ps
```

Apply future releases with a backup, `git pull`, and the same `up --build -d` command. Back up the PostgreSQL, Qdrant, Redis and upload volumes before upgrades.
