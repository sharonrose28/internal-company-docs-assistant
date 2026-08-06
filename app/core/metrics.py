from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "docs_http_requests_total", "HTTP requests", ("method", "route", "status")
)
HTTP_LATENCY = Histogram(
    "docs_http_request_duration_seconds", "HTTP request latency", ("method", "route")
)
AUTH_ATTEMPTS = Counter("docs_auth_attempts_total", "Authentication attempts", ("outcome",))
UPLOADS = Counter("docs_uploads_total", "Document uploads", ("type", "outcome"))
QUERIES = Counter("docs_queries_total", "Assistant queries", ("outcome",))
PERMISSION_FAILURES = Counter(
    "docs_permission_failures_total", "Authorization failures", ("operation",)
)
OPERATION_LATENCY = Histogram(
    "docs_operation_duration_seconds",
    "External and pipeline operation latency",
    ("operation", "outcome"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
