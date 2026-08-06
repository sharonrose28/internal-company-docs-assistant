import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

import structlog

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)

_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """One-line ECS-inspired JSON formatter for API, worker, and library logs."""

    def format(self, record: logging.LogRecord) -> str:
        structured = record.msg if isinstance(record.msg, dict) else None
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        if structured:
            payload.update(structured)
            payload["event"] = str(structured.get("event", "structured_event"))
        if request_id := request_id_ctx.get():
            payload["request_id"] = request_id
        if user_id := user_id_ctx.get():
            payload["user_id"] = user_id
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"), ensure_ascii=False)


def configure_logging(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(numeric_level)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "celery"):
        target = logging.getLogger(name)
        target.handlers.clear()
        target.propagate = True

    # Existing structured events continue through Python's logging hierarchy.
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
