# Redis cache strategy

All cache entries expire after 900 seconds (15 minutes). Celery continues to use Redis database 0, while application caching defaults to Redis database 1 to prevent worker traffic and result eviction from interfering with request caching.

## Cached data

- `answer`: successful recent question responses, including validated citations.
- `retrieval`: authorized top-five Qdrant results and metadata.
- `query-embedding`: dense OpenAI query vectors and sparse BM25 query vectors. Document vectors remain in Qdrant and are not duplicated in Redis.
- `chat-history`: paginated session history for a user.

Questions are normalized and SHA-256 hashed in keys; raw question text is not embedded in Redis keys. Answer and retrieval keys include an authorization fingerprint derived from user ID, role, and department. Query embeddings are independent of permissions and may be shared for identical normalized questions.

## Authorization and invalidation

Every answer and retrieval cache hit is reauthorized against PostgreSQL before content is returned. Cache entries never replace RBAC checks.

Keys include a global document-generation number. Document indexing completion, deletion, and assignment changes increment that number through retryable Celery tasks. Old keys immediately become unreachable and expire naturally, avoiding expensive Redis `SCAN`/`DEL` operations. Chat history uses a per-user version that advances after a new message transaction commits.

If Redis is unavailable, reads miss and writes/invalidation log structured warnings; requests continue against PostgreSQL, Qdrant, and OpenAI. Invalidation tasks retry. PostgreSQL post-authorization prevents stale permission leakage even during an invalidation delay.

## Production controls

- Use a private Redis endpoint with TLS, authentication, encryption at rest, and disabled public access.
- Set an explicit memory limit and an LRU/LFU eviction policy appropriate for ephemeral cache data.
- Monitor hit rate, latency, eviction count, memory pressure, invalidation failures, and post-authorization mismatches.
- Do not cache refusals by default; newly indexed evidence should become available immediately after generation invalidation.
- Consider request coalescing for highly repetitive questions if cache stampedes appear in production metrics.
