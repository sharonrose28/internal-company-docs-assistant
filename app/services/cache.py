import hashlib
import json
from typing import Any

from redis.asyncio import Redis
import structlog

from app.core.config import Settings
from app.models.user import User

logger = structlog.get_logger()


class CacheService:
    """Best-effort Redis cache with generation invalidation and authorization-scoped keys."""

    GENERATION_KEY = "docs-cache:generation"

    def __init__(self, settings: Settings, client: Redis | None = None):
        self.ttl = settings.cache_ttl_seconds
        self.client = client or Redis.from_url(settings.cache_redis_url, decode_responses=True)

    async def generation(self) -> int:
        try:
            value = await self.client.get(self.GENERATION_KEY)
            return int(value or 0)
        except Exception as exc:
            logger.warning("cache_generation_read_failed", error_type=type(exc).__name__)
            return 0

    async def history_version(self, user_id: str) -> int:
        try:
            value = await self.client.get(f"chat-history:version:{user_id}")
            return int(value or 0)
        except Exception as exc:
            logger.warning("cache_history_version_read_failed", error_type=type(exc).__name__)
            return 0

    async def bump_history(self, user_id: str) -> None:
        try:
            key = f"chat-history:version:{user_id}"
            await self.client.incr(key)
            await self.client.expire(key, self.ttl * 2)
        except Exception as exc:
            logger.warning("cache_history_invalidation_failed", error_type=type(exc).__name__)

    async def get_json(self, key: str) -> Any | None:
        try:
            value = await self.client.get(key)
            return json.loads(value) if value is not None else None
        except Exception as exc:
            logger.warning("cache_read_failed", cache_type=key.split(":", 1)[0], error_type=type(exc).__name__)
            return None

    async def set_json(self, key: str, value: Any) -> None:
        try:
            await self.client.set(key, json.dumps(value, separators=(",", ":")), ex=self.ttl)
        except Exception as exc:
            logger.warning("cache_write_failed", cache_type=key.split(":", 1)[0], error_type=type(exc).__name__)

    async def delete(self, key: str) -> None:
        try:
            await self.client.delete(key)
        except Exception as exc:
            logger.warning("cache_delete_failed", cache_type=key.split(":", 1)[0], error_type=type(exc).__name__)

    @staticmethod
    def question_hash(question: str) -> str:
        normalized = " ".join(question.casefold().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def scope(user: User) -> str:
        raw = f"{user.id}:{user.role.value}:{user.department_id or '-'}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def answer_key(
        self, generation: int, user: User, question: str, memory_fingerprint: str = "none"
    ) -> str:
        return (
            f"answer:v2:g{generation}:{self.scope(user)}:{memory_fingerprint}:"
            f"{self.question_hash(question)}"
        )

    def retrieval_key(self, generation: int, user: User, question: str, mode: str, filters: dict) -> str:
        filter_hash = hashlib.sha256(
            json.dumps(filters, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:20]
        return (
            f"retrieval:v1:g{generation}:{self.scope(user)}:{mode}:"
            f"{filter_hash}:{self.question_hash(question)}"
        )

    def embedding_key(self, question: str, model: str, mode: str) -> str:
        return f"query-embedding:v1:{model}:{mode}:{self.question_hash(question)}"

    @staticmethod
    def history_key(user_id: str, session_id: str, version: int, offset: int, limit: int) -> str:
        return f"chat-history:v3:{user_id}:{session_id}:v{version}:{offset}:{limit}"
