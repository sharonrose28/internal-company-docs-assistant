# Internal Company Docs Assistant

A production-oriented, permission-aware retrieval-augmented generation (RAG) system for internal company knowledge. It ingests PDF, Markdown, and Slack export documents, indexes authorized chunks in Qdrant, and answers questions with citations only when the available evidence is trustworthy.

## Architecture at a glance

```text
React + Vite frontend
        |
        | JWT-authenticated HTTPS/JSON
        v
FastAPI routers -> dependencies -> services -> repositories
        |                |              |
        |                |              +--> PostgreSQL
        |                +-----------------> Redis cache
        |                +-----------------> Qdrant
        |                +-----------------> OpenAI
        |
        +--> Redis/Celery broker -> Celery workers
                                     |--> document extraction/chunking
                                     |--> OpenAI embeddings
                                     |--> Qdrant vector updates
                                     +--> cache invalidation/cleanup
```

The API is organized as a clean layered application:

- **Routers** define HTTP contracts and status codes.
- **Dependencies** construct authenticated users, database sessions, repositories, and services.
- **Services** implement authentication, document management, retrieval, memory, generation, citations, caching, auditing, and RAG orchestration.
- **Repositories** are the PostgreSQL persistence boundary.
- **Workers** execute slow and retryable ingestion operations outside request processes.
- **Schemas** are Pydantic v2 API and service contracts.
- **Models** are SQLAlchemy persistence entities.

## Runtime components

| Component | Responsibility |
|---|---|
| React frontend | Login, document management, conversations, citations, themes, loading and error states |
| FastAPI | Authentication, validation, authorization, APIs, dependency injection and RAG orchestration |
| PostgreSQL | Source of truth for users, departments, documents, chunks, assignments, jobs, conversations and audits |
| Qdrant | Dense and sparse vector retrieval with metadata and permission filters |
| Redis DB 0 | Celery broker and result backend |
| Redis DB 1 | Query, embedding, retrieval, answer and history caches |
| Celery worker | Extraction, chunking, embedding, vector writes, deletion and permission synchronization |
| Celery Beat | Scheduled maintenance task dispatch |
| Flower | Celery task monitoring UI |
| OpenAI | `text-embedding-3-small` embeddings and grounded answer generation |

## Repository structure

```text
app/
  api/
    routes/              # auth, documents, search, chat and health HTTP handlers
    dependencies.py      # dependency injection and authenticated-user construction
  core/                  # settings, JWT/password security, RBAC, errors, logging, metrics
  db/                    # SQLAlchemy base and async session management
  ingestion/             # PDF, Markdown, Slack parsers and token-aware chunkers
  models/                # SQLAlchemy models
  repositories/          # database access and authorization-aware queries
  schemas/               # Pydantic v2 request/response contracts
  services/              # application and domain orchestration
  workers/               # Celery configuration and ingestion tasks
alembic/                 # database migrations
docs/                    # focused security, caching, citation and indexing documentation
frontend/
  src/
    api/                 # Axios client, endpoint functions, query keys and API types
    app/                 # providers and route composition
    components/          # reusable UI, layout and error boundary components
    features/            # authentication, chat and document vertical features
    lib/                 # framework-independent helpers
    stores/              # small Zustand client stores
    styles/              # Tailwind and semantic theme tokens
tests/                   # unit, repository, API, permission and RAG tests
docker-compose.yml       # backend runtime topology
Dockerfile               # shared API/worker image
```

## Authentication flow

```text
POST /login
  -> validate Pydantic request
  -> look up user by normalized email
  -> verify password hash
  -> verify account is active
  -> issue short-lived signed JWT
  -> frontend stores token in sessionStorage
  -> Axios attaches Authorization: Bearer <token>
```

Protected requests decode and validate the token issuer, audience, expiry, subject, and token version. The current user is loaded from PostgreSQL for every protected operation. A disabled account, invalid token, or stale token version is rejected before reaching a domain service.

The current browser implementation uses `sessionStorage`, which limits persistence to the browser session. A hardened internet-facing deployment should prefer a Secure, HttpOnly, SameSite cookie plus CSRF protection.

## Authorization and RBAC flow

The application fails closed. Authorization is applied before document content is returned, before vector candidates are accepted, and before context is sent to the LLM.

| Role | Document access |
|---|---|
| Admin | All documents |
| Manager | Documents belonging to the manager's department |
| Employee | Only documents explicitly assigned through `document_assignments` |

Authorization has two layers:

1. Qdrant receives role/department/assignment metadata filters so unauthorized vectors are excluded during retrieval.
2. Retrieved document IDs are checked again against PostgreSQL, the source of truth, before passages can enter the prompt.

Assignment changes enqueue a permission synchronization task that updates Qdrant payloads. The PostgreSQL post-check prevents temporary synchronization lag from leaking content. Direct document endpoints use the same rules and return `403` when a known resource is not permitted.

## Document upload and ingestion flow

```text
POST /upload
  -> authenticate user
  -> verify upload permission and department membership
  -> validate extension, media type and size
  -> stream file to controlled upload storage
  -> calculate SHA-256 checksum
  -> create Document(status=uploaded)
  -> create IngestionJob(status=queued)
  -> commit transaction
  -> enqueue documents.extract Celery workflow
  -> return HTTP 202

Celery worker
  -> mark document/job processing
  -> select parser by document type
  -> extract structured text
  -> create approximately 500-token chunks with 100-token overlap
  -> persist DocumentChunk rows
  -> batch embedding jobs
  -> write vectors and metadata to Qdrant
  -> save vector IDs/checksums in PostgreSQL
  -> mark chunks/document/job complete
  -> increment Redis cache generation
```

The Celery task is queued only after the API transaction commits, preventing a worker from attempting to load a document or job that is not yet visible in PostgreSQL.

### PDF ingestion

`PyMuPDF` extracts native text page by page. Page numbers are retained in chunk metadata. Pages without usable native text are considered scanned/image-only and intentionally skipped; OCR is not silently attempted. The semantic chunker tries to preserve natural paragraph/section boundaries while targeting the configured token size and overlap.

### Markdown ingestion

The CommonMark-oriented parser treats H1, H2 and H3 headings as section boundaries. Each chunk retains:

- complete heading hierarchy (`heading_path`),
- current section,
- one-based start and end line numbers,
- filename and department.

Long sections are split token-wise without losing their heading context.

### Slack export ingestion

The Slack parser extracts channel, resolved username, timestamp, message text, thread replies and participants. It ignores system notifications, image-only messages and emoji-only messages. Threaded messages remain grouped; unthreaded messages are grouped into logical channel conversations. Chunks retain channel, thread and participant metadata.

### Embedding and deduplication

The embedding service uses LangChain `OpenAIEmbeddings` with `text-embedding-3-small`. Celery embeds chunks in configurable batches and retries transient failures with exponential backoff. Document SHA-256 and chunk embedding checksums avoid repeated work. Qdrant point IDs are stored in `document_chunks.vector_id`, making deletion and repair deterministic.

## Retrieval flow

```text
query
  -> authenticate and build permission scope
  -> normalize/filter request
  -> obtain or generate query embedding
  -> Qdrant hybrid or semantic search
       dense vector similarity
       + sparse BM25 relevance
       + department/assignment/document metadata filters
  -> retrieve candidate set
  -> PostgreSQL authorization post-check
  -> rank and return top 5 authorized passages
```

Hybrid search is the default because dense vectors capture meaning while BM25 preserves exact names, acronyms and policy terms. The candidate pool is larger than five so ranking and authorization checks still produce up to five final results. Qdrant payload indexes support document, department and permission filters without scanning the full collection.

`POST /search` exposes retrieval directly and returns chunk text, score, metadata, page number and document ID. See `docs/indexing-strategy.md` for collection and payload-index details.

## RAG question-answering flow

```text
POST /chat
  -> JWT authentication
  -> load/create a user-owned chat session
  -> load at most 10 previous exchanges
  -> check permission-scoped answer cache
  -> create a memory-aware retrieval query
  -> permission-filtered hybrid Qdrant retrieval
  -> PostgreSQL authorization verification
  -> discard passages below similarity threshold
  -> build bounded, source-labelled context
  -> ask LLM for structured grounded output
  -> detect unsupported or contradictory evidence
  -> validate every citation against supplied sources
  -> enforce minimum generation confidence
  -> render answer and separate citation objects
  -> persist chat message
  -> write audit event
  -> cache successful response
```

The context builder assigns stable source labels such as `S1` and includes only the selected passage text and safe metadata. Retrieved documents are untrusted data, not instructions; prompt construction separates evidence from system rules.

### Citations

Each successful citation includes:

- document ID and document name,
- page number when available,
- section heading when available,
- similarity score,
- supporting quote,
- internal source identifier.

Citation identifiers produced by the model must match sources that were actually provided. Invalid, missing, or invented citations cause refusal instead of an ungrounded answer. The response returns both readable attribution in the answer and structured citations for the frontend.

### Refusal behavior

The public refusal is deliberately non-disclosing:

> I couldn't find enough trusted information in the documents available to you.

It is returned when no authorized evidence exists, all scores are below threshold, the context is empty, sources contradict one another, requested information is absent, model confidence is too low, or citation validation fails. Internal audit outcomes preserve the operational reason without revealing whether inaccessible documents exist.

Default thresholds are configured through `RAG_HYBRID_SCORE_THRESHOLD`, `RAG_SEMANTIC_SCORE_THRESHOLD`, and `RAG_MIN_CONFIDENCE`. They are starting points and should be calibrated against a labelled internal evaluation set. See `docs/refusal-policy.md`.

## Conversational memory

Each chat session belongs to one user. PostgreSQL stores sessions and messages, including confidence and citations. Follow-up questions load only the latest ten exchanges from the owned session. Memory is used to resolve conversational references and improve the retrieval query; it does not broaden document authorization.

The frontend supports multiple sessions, lists recent conversations, loads history in chronological order, and can delete an owned conversation with all messages through cascading database deletion.

## Cache architecture

Redis uses a default 15-minute TTL for:

- normalized query embeddings,
- permission-scoped retrieval results,
- successful answers,
- recent session history.

Cache keys include user authorization context and a global document generation. Uploads, deletions and permission changes increment the generation, making old keys unreachable without an expensive wildcard deletion. Cached answers are rechecked against PostgreSQL authorization before reuse.

Redis cache failures degrade to normal computation; they do not bypass permissions or make the API unavailable. See `docs/cache-strategy.md`.

## PostgreSQL data model

| Table | Purpose |
|---|---|
| `users` | Email, password hash, role, department, active state and token version |
| `departments` | Department identity |
| `documents` | File identity, checksum, storage, department, owner and processing status |
| `document_chunks` | Text, source metadata, embedding checksum/vector ID and chunk status |
| `document_assignments` | Explicit employee-to-document permissions |
| `ingestion_jobs` | Celery task, stage, progress, attempts and failure details |
| `chat_sessions` | User-owned conversation containers |
| `chat_messages` | Questions, answers, confidence and structured citations |
| `audit_events` | Hashed question identity, outcome, document/chunk IDs, model and latency |

Alembic owns schema evolution. Application containers run `alembic upgrade head` through the one-shot `migrate` service before API and workers start.

## API surface

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/login` | Authenticate and issue JWT |
| `POST` | `/upload` | Store a document and queue ingestion |
| `GET` | `/documents` | List authorized documents |
| `GET` | `/documents/{id}` | Read authorized document metadata |
| `DELETE` | `/documents/{id}` | Delete metadata and enqueue file/vector cleanup |
| `PUT` | `/documents/{id}/assignments/{user_id}` | Assign employee access |
| `DELETE` | `/documents/{id}/assignments/{user_id}` | Remove employee access |
| `POST` | `/search` | Run permission-filtered retrieval |
| `POST` | `/chat` | Run the complete RAG pipeline |
| `GET` | `/chat/sessions` | List owned conversations |
| `POST` | `/chat/sessions` | Create a conversation |
| `DELETE` | `/chat/sessions/{id}` | Delete an owned conversation and messages |
| `GET` | `/chat/history?session_id=...` | Read chronological owned history |
| `GET` | `/health` | Database-backed liveness check |

Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

## Frontend architecture and flow

```text
AppProviders
  -> QueryClientProvider
  -> BrowserRouter
  -> route-aware ErrorBoundary
  -> AppRouter
       -> LoginPage (public)
       -> ProtectedRoute
            -> AppShell
                 -> responsive sidebar and conversation list
                 -> ChatPage or DocumentsPage
  -> ToastRegion
```

TanStack Query owns server state, request deduplication, staleness and mutation invalidation. Zustand is restricted to token, theme and transient toast state. React Hook Form and Zod validate forms. Axios is the only HTTP boundary and attaches JWTs centrally. Feature routes are lazy loaded, React Markdown renders answers without raw HTML, and Framer Motion is limited to small orientation-preserving transitions.

The chat UI appends questions at the bottom, reveals completed answers progressively, keeps the send button inside the composer, auto-scrolls safely, and reloads persisted history by session. The route-aware error boundary allows recovery while recording the real client exception for diagnosis.

See `frontend/ARCHITECTURE.md` for frontend-specific design details.

## Logging, auditing and metrics

The backend emits structured JSON logs with request IDs and relevant user/request context. It records authentication outcomes, uploads, permission failures, query outcomes and retrieval, Qdrant, embedding and LLM latency without logging raw passwords, JWTs, document text or complete questions.

Prometheus metrics track HTTP behavior and critical pipeline latency/counts. Audit events are stored independently from ordinary application logs and use a question hash plus authorized document/chunk IDs to support investigation without duplicating sensitive question text.

## Exception handling

Domain exceptions are translated centrally into consistent JSON responses. Validation failures return client-safe details; permission failures return `403`; authentication failures return `401`; unexpected exceptions return a generic `500` and retain diagnostic detail only in structured logs. The frontend converts API failures into accessible toast notifications rather than exposing stack traces.

## Deployment topology

Docker Compose creates:

- an `edge` network for host-exposed API and Flower,
- an internal `backend` network for PostgreSQL, Redis and Qdrant,
- an `egress` network for workers that call OpenAI,
- persistent volumes for uploads, PostgreSQL, Redis, Qdrant and Celery Beat.

PostgreSQL, Redis and Qdrant are not published to the host. API and Flower bind to `127.0.0.1` by default. Every long-running service has a health check and restart policy. The frontend currently runs as a separate Vite development process; production should build static assets and serve them from a same-origin reverse proxy/CDN that forwards `/api` to FastAPI.

For multi-host production, replace local upload storage with durable object storage, use managed PostgreSQL/Redis/Qdrant where appropriate, terminate TLS at a reverse proxy/load balancer, run multiple API replicas, and scale Celery independently by queue depth.

## Local setup

### 1. Configure environment

```powershell
Copy-Item .env.example .env
```

Set at least:

- `POSTGRES_PASSWORD`
- `JWT_SECRET` (at least 32 random characters)
- `OPENAI_API_KEY`
- `FLOWER_BASIC_AUTH` (for example `floweradmin:a-strong-password`)

### 2. Start backend services

Docker Desktop must be running with the Linux container engine.

```powershell
docker compose up --build -d
docker compose ps
```

Migrations run automatically through the `migrate` service.

### 3. Create a user

```powershell
docker compose exec api python -m app.cli.create_user --email admin@example.com --role admin
```

The command prompts for the password. Managers and employees require an appropriate department relationship before department-scoped operations.

### 4. Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://localhost:8000`.

## Operations and troubleshooting

```powershell
# Service status
docker compose ps

# API and worker logs
docker compose logs --since=10m api worker

# Follow ingestion tasks
docker compose logs -f worker

# API health
Invoke-RestMethod http://localhost:8000/health

# Apply migrations manually
docker compose run --rm migrate
```

Flower is available at `http://localhost:5555/flower` when configured and running.

Document status moves through `uploaded -> processing -> ready` or `failed`. `ingestion_jobs.stage`, `progress`, `attempts`, and `error_message` provide task-level diagnostics. Worker retries are bounded by `MAX_INGESTION_ATTEMPTS`.

## Tests

Activate the virtual environment and invoke pytest through Python so Windows does not depend on a global `pytest` executable:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
```

The suite includes unit, repository, API, permission and RAG pipeline tests. OpenAI, Qdrant, Redis and Celery boundaries use deterministic mocks/fakes. Coverage is branch-aware, written to `coverage.xml`, and configured for a 90% minimum.

Frontend verification:

```powershell
cd frontend
npm run lint
npm run build
```

## Security invariants

1. No retrieved text reaches the LLM before Qdrant filtering and PostgreSQL authorization verification.
2. Cache entries never grant access and are scoped by authorization context.
3. Missing or contradictory evidence produces refusal, not speculation.
4. Citation IDs must correspond to supplied context.
5. Uploaded filenames never directly control arbitrary filesystem paths.
6. Passwords are hashed; JWT secrets, API keys and database credentials come from environment secrets.
7. Sensitive content is excluded from logs and public errors.
8. Document/permission changes invalidate caches and synchronize vector metadata.

Additional details are available in `docs/security.md`, `docs/citations.md`, `docs/cache-strategy.md`, `docs/conversational-memory.md`, `docs/indexing-strategy.md`, and `docs/refusal-policy.md`.

Railway-specific topology, variables, service creation and verification steps are documented in `docs/railway-deployment.md`.

Single-server Docker deployment, including the freevps.edu.pl-compatible topology, is documented in `docs/vps-deployment.md`.

Using Neon as the managed PostgreSQL database for the VPS deployment is documented in `docs/neon-deployment.md`.

A no-card, free-tier demonstration deployment using Render, Neon, Upstash and Qdrant Cloud is documented in `docs/render-deployment.md`.
