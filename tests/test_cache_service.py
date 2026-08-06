from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.user import Role
from app.services.cache import CacheService


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.last_ttl = None

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None):
        self.values[key] = value
        self.last_ttl = ex

    async def delete(self, key):
        self.values.pop(key, None)

    async def incr(self, key):
        self.values[key] = str(int(self.values.get(key, 0)) + 1)
        return int(self.values[key])

    async def expire(self, _key, _ttl):
        return True


@pytest.mark.asyncio
async def test_json_cache_uses_fifteen_minute_ttl():
    redis = FakeRedis()
    cache = CacheService(Settings(jwt_secret="x" * 32), redis)
    await cache.set_json("answer:test", {"answer": "cached"})
    assert await cache.get_json("answer:test") == {"answer": "cached"}
    assert redis.last_ttl == 900


def test_answer_keys_are_user_and_role_scoped():
    cache = CacheService(Settings(jwt_secret="x" * 32), FakeRedis())
    first = SimpleNamespace(id=uuid4(), role=Role.EMPLOYEE, department_id=uuid4())
    second = SimpleNamespace(id=uuid4(), role=Role.ADMIN, department_id=None)
    assert cache.answer_key(3, first, "Leave policy?") != cache.answer_key(
        3, second, "Leave policy?"
    )
    assert cache.answer_key(3, first, "Leave policy?") != cache.answer_key(
        4, first, "Leave policy?"
    )

