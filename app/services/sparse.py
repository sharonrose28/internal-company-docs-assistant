"""Small, deterministic lexical encoder for Qdrant hybrid search.

Feature hashing keeps lexical indexing available in memory-constrained deployments
without loading an ONNX runtime and model into both the API and Celery processes.
"""

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
import re

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:['_-][a-z0-9]+)*", re.IGNORECASE)
HASH_SPACE = 2**31 - 1


@dataclass(frozen=True, slots=True)
class SparseVector:
    indices: list[int]
    values: list[float]


class HashedSparseEncoder:
    """Feature-hashed term frequencies; Qdrant applies collection-level IDF."""

    @staticmethod
    def _encode(text: str) -> SparseVector:
        counts: Counter[int] = Counter()
        for token in TOKEN_PATTERN.findall(text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            counts[int.from_bytes(digest, "big") % HASH_SPACE] += 1
        indices = sorted(counts)
        return SparseVector(
            indices=indices,
            values=[1.0 + math.log(counts[index]) for index in indices],
        )

    def embed(self, texts: list[str]):
        for text in texts:
            yield self._encode(text)

    def query_embed(self, query: str):
        yield self._encode(query)
