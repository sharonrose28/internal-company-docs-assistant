from types import SimpleNamespace
from uuid import uuid4

from app.core.config import Settings
from app.services.embedding import EmbeddingItem, EmbeddingService


class FakeEmbeddings:
    def __init__(self):
        self.calls = []

    def embed_documents(self, texts):
        self.calls.append(texts)
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeSparseEmbeddings:
    def embed(self, texts):
        return [SimpleNamespace(indices=Array([1, 2]), values=Array([0.5, 0.7])) for _ in texts]


class Array(list):
    def tolist(self):
        return list(self)


class FakeQdrant:
    def __init__(self, reusable_id):
        self.reusable_id = reusable_id
        self.points = []

    def collection_exists(self, _):
        return True

    def retrieve(self, **_):
        return [SimpleNamespace(id=self.reusable_id, vector={"dense": [0.4, 0.5, 0.6]})]

    def get_collection(self, _):
        vectors = SimpleNamespace(size=3)
        return SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(vectors={"dense": vectors})))

    def upsert(self, *, points, **_):
        self.points.extend(points)

    def create_payload_index(self, **_):
        return None


def test_batches_new_text_and_reuses_checksum_match_without_embedding_call():
    reusable_id = str(uuid4())
    embeddings = FakeEmbeddings()
    qdrant = FakeQdrant(reusable_id)
    service = EmbeddingService(
        Settings(jwt_secret="x" * 32, openai_api_key="test-key"),
        embeddings=embeddings,
        sparse_embeddings=FakeSparseEmbeddings(),
        qdrant=qdrant,
    )
    reused_chunk, new_chunk = uuid4(), uuid4()
    result = service.embed_and_store([
        EmbeddingItem(reused_chunk, "same document chunk", {"kind": "reused"}, reusable_id),
        EmbeddingItem(new_chunk, "new chunk", {"kind": "new"}),
    ])

    assert embeddings.calls == [["new chunk"]]
    assert result == {reused_chunk: str(reused_chunk), new_chunk: str(new_chunk)}
    assert len(qdrant.points) == 2
    vectors = {str(point.id): point.vector["dense"] for point in qdrant.points}
    assert vectors[str(reused_chunk)] == [0.4, 0.5, 0.6]
    assert vectors[str(new_chunk)] == [0.1, 0.2, 0.3]
