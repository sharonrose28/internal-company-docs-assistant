# Retrieval-Augmented Generation pipeline

1. FastAPI authenticates the JWT and loads the active PostgreSQL user.
2. `RetrievalService` derives Qdrant filters from the user's role and assignments. Dense and sparse candidates are filtered before fusion, and returned document IDs are verified against PostgreSQL.
3. LangChain embeds the question with `text-embedding-3-small` while the local BM25 sparse query is generated concurrently.
4. Qdrant returns at most five authorized hybrid-search passages.
5. `ContextBuilder` serializes passages as token-bounded JSON records with stable source IDs.
6. `AnswerGenerator` sends the question and authorized context through LangChain using the Responses API and structured output.
7. `CitationService` rejects unknown, undeclared, or mismatched source markers and constructs citations from retrieval metadata.
8. `RAGService` refuses answers with insufficient evidence, invalid citations, or confidence below the configured threshold.
9. The response is stored in chat history. `AuditService` independently records a question hash, outcome, model, latency, authorized document IDs, and cited chunk IDs without retaining another copy of the raw question or answer.

Retrieved content is treated as untrusted data. The system prompt tells the model not to execute instructions contained in documents and prevents use of prior knowledge. An authorization failure or audit-write failure prevents an answer from being returned.
