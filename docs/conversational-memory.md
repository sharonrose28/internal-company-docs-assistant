# Conversational memory

Each user may own multiple `chat_sessions`. Every `chat_messages` row belongs to exactly one session and stores one question/answer exchange with its citations. Existing pre-session messages are migrated into one deterministic legacy session per user.

`POST /chat` accepts an optional `session_id`. If omitted, the service creates a session titled from the first question. `POST /chat/sessions` creates an explicit session, `GET /chat/sessions` lists the user's sessions, and `GET /chat/history?session_id=...` returns session-specific history.

Before answering a follow-up, `ConversationMemoryService` loads at most the ten most recent exchanges. The last five questions contextualize retrieval; all ten exchanges are supplied to generation as untrusted JSON. Prior conversation can resolve references such as “What about contractors?”, but it is never treated as documentary evidence—the current authorized Qdrant passages remain the only factual source.

Previous questions remain available because the user authored them. Previous answers are included only when all cited documents are still authorized in PostgreSQL. This prevents permission revocation from leaking document-derived content back into the model context.

Answer cache keys include the session memory fingerprint, preventing identical questions in different conversations from sharing context-dependent answers. Session-history cache versions advance only after message transactions commit.
