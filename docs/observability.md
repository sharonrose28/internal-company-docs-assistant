# Observability

The API and Celery workers write one JSON object per line to stdout. The stable base fields are
`timestamp`, `level`, `logger`, `event`, `request_id`, and (after authentication) `user_id`.
Application events add identifiers and timings, but never passwords, JWTs, document content,
questions, retrieved passages, embedding vectors, or LLM prompts.

Prometheus metrics are exposed at `GET /metrics`. Key series include HTTP request count/latency,
authentication outcomes, uploads, query outcomes, permission failures, and operation latency for
retrieval, embeddings, Qdrant, and the LLM. Metric labels are deliberately low-cardinality and do
not contain tenant or user-controlled values except the normalized FastAPI route template.

In production, collect stdout with the platform log agent and restrict `/metrics` to the internal
monitoring network (or protect it at the ingress/service-mesh layer). Alert on elevated 5xx rates,
permission failures, authentication failures, worker task failures, and latency histogram SLOs.
