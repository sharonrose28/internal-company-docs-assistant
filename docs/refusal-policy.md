# Refusal policy and threshold selection

The public refusal response is deliberately identical for missing, inaccessible, weak, or contradictory evidence:

> I couldn't find enough trusted information in the documents available to you.

This prevents the response from revealing whether an inaccessible document exists. Internally, audit events distinguish `no_authorized_evidence`, `below_similarity_threshold`, `contradictory_evidence`, `requested_information_missing`, `invalid_citations`, and low-confidence generation.

## Decision order

1. Qdrant applies role and assignment filters before retrieving candidates; PostgreSQL verifies returned document IDs.
2. Passages below the configured retrieval threshold are removed. If none remain, the LLM is not called.
3. Structured generation classifies materially conflicting passages as contradictory and absent requested facts as unsupported.
4. The service refuses contradictory or unsupported evidence, confidence below `RAG_MIN_CONFIDENCE`, missing citations, or invalid citation provenance.

## Selecting thresholds

The defaults are bootstrap values, not universal constants:

- Hybrid RRF score: `0.20`
- Dense cosine similarity: `0.35`
- Grounded-answer confidence: `0.60`

Hybrid fusion scores and dense cosine scores have different distributions and must be calibrated separately. Build a labeled evaluation set containing answerable questions, unrelated questions, permission-denied questions, missing facts, and contradictory document versions. Sweep candidate thresholds and measure grounded-answer precision, refusal precision/recall, citation correctness, and false-answer rate.

For internal company documentation, choose the lowest threshold that still meets the required grounded-answer precision, giving false answers substantially more cost than conservative refusals. Validate by department and document type, then monitor score distributions and refusal rates after embedding, chunking, or Qdrant-index changes. Recalibrate rather than copying thresholds between models or fusion strategies.
