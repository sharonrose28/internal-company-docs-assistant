from app.services.sparse import HashedSparseEncoder


def test_sparse_encoder_is_deterministic_and_counts_terms():
    encoder = HashedSparseEncoder()
    first = next(encoder.query_embed("Policy policy benefits"))
    second = next(encoder.query_embed("Policy policy benefits"))

    assert first == second
    assert first.indices == sorted(first.indices)
    assert len(first.indices) == 2
    assert max(first.values) > min(first.values)


def test_sparse_encoder_handles_empty_text():
    vector = next(HashedSparseEncoder().embed([""]))
    assert vector.indices == []
    assert vector.values == []
