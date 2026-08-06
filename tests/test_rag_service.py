from uuid import uuid4
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.models.user import Role, User
from app.schemas.chat import ChatRequest
from app.schemas.search import SearchResult
from app.services.generation import GroundedAnswer
from app.services.rag import RAGService


class FakeRetrieval:
    def __init__(self, results):
        self.results = results
        self.authorizer = None

    async def search(self, _query, _user, authorizer, _mode):
        self.authorizer = authorizer
        return self.results


class FakeGenerator:
    def __init__(self, answer=None):
        self.answer = answer
        self.called = False

    async def generate(self, _question, _context, _memory="[]"):
        self.called = True
        return self.answer


class FakeChats:
    def __init__(self):
        self.messages = []

    async def add(self, message):
        self.messages.append(message)


class FakeAudit:
    def __init__(self):
        self.events = []

    async def record(self, **event):
        self.events.append(event)


class FakeMemory:
    def __init__(self):
        self.session_id = uuid4()

    async def load(self, _user, session_id, _question):
        return SimpleNamespace(
            session=SimpleNamespace(id=session_id or self.session_id),
            exchanges=(),
            fingerprint="empty-memory",
        )

    @staticmethod
    def retrieval_query(question, _memory):
        return question

    @staticmethod
    def prompt_context(_memory):
        return "[]"


@pytest.mark.asyncio
async def test_rag_generates_grounded_answer_with_validated_citation():
    document_id, chunk_id = uuid4(), uuid4()
    result = SearchResult(
        chunk="Privileged credentials rotate every 90 days.",
        score=0.9,
        metadata={
            "chunk_id": str(chunk_id), "filename": "Security.pdf", "page": 4,
            "section": "Credential Rotation",
        },
        page_number=4,
        document_id=document_id,
    )
    documents, chats, audit = object(), FakeChats(), FakeAudit()
    retrieval = FakeRetrieval([result])
    generator = FakeGenerator(GroundedAnswer(
        answer="According to [S1], privileged credentials rotate every 90 days.",
        supported=True,
        confidence=0.91,
        citation_ids=["S1"],
    ))
    service = RAGService(
        Settings(jwt_secret="x" * 32, openai_api_key="test-key"),
        retrieval, documents, chats, generator, audit, FakeMemory(),
    )
    user = User(id=uuid4(), email="admin@example.com", password_hash="x", role=Role.ADMIN,
                department_id=None, is_active=True, token_version=1)

    response = await service.ask(ChatRequest(question="When do credentials rotate?"), user)

    assert retrieval.authorizer is documents
    assert response.status == "answered"
    assert response.answer == (
        "According to Security.pdf (Page 4, Credential Rotation), "
        "privileged credentials rotate every 90 days."
    )
    assert response.citations[0].document_id == document_id
    assert response.citations[0].document_name == "Security.pdf"
    assert response.citations[0].page_number == 4
    assert response.citations[0].section_heading == "Credential Rotation"
    assert response.citations[0].similarity_score == 0.9
    assert audit.events[0]["chunk_ids"] == [str(chunk_id)]
    assert len(chats.messages) == 1


@pytest.mark.asyncio
async def test_rag_refuses_without_authorized_evidence_and_does_not_call_llm():
    generator, audit = FakeGenerator(), FakeAudit()
    service = RAGService(
        Settings(jwt_secret="x" * 32, openai_api_key="test-key"),
        FakeRetrieval([]), object(), FakeChats(), generator, audit, FakeMemory(),
    )
    user = User(id=uuid4(), email="employee@example.com", password_hash="x", role=Role.EMPLOYEE,
                department_id=uuid4(), is_active=True, token_version=1)

    response = await service.ask(ChatRequest(question="What is the restricted policy?"), user)

    assert response.status == "insufficient_evidence"
    assert not generator.called
    assert audit.events[0]["outcome"] == "no_authorized_evidence"


@pytest.mark.asyncio
async def test_rag_refuses_when_all_passages_are_below_threshold():
    result = SearchResult(
        chunk="Unrelated material.", score=0.10,
        metadata={"chunk_id": str(uuid4()), "filename": "Notes.pdf"},
        page_number=1, document_id=uuid4(),
    )
    generator, audit = FakeGenerator(), FakeAudit()
    service = RAGService(
        Settings(jwt_secret="x" * 32, openai_api_key="test-key"),
        FakeRetrieval([result]), object(), FakeChats(), generator, audit, FakeMemory(),
    )
    user = User(id=uuid4(), email="admin@example.com", password_hash="x", role=Role.ADMIN,
                department_id=None, is_active=True, token_version=1)

    response = await service.ask(ChatRequest(question="What is the leave policy?"), user)

    assert response.answer == "I couldn't find enough trusted information in the documents available to you."
    assert not generator.called
    assert audit.events[0]["outcome"] == "below_similarity_threshold"


@pytest.mark.asyncio
async def test_rag_refuses_materially_contradictory_passages():
    results = [SearchResult(
        chunk="The allowance is 20 days.", score=0.8,
        metadata={"chunk_id": str(uuid4()), "filename": "Policy.pdf"},
        page_number=2, document_id=uuid4(),
    )]
    generator = FakeGenerator(GroundedAnswer(
        answer="The sources conflict.", supported=False, contradictory=True,
        confidence=0.2, citation_ids=[], evidence_reason="Conflicting allowance values",
    ))
    audit = FakeAudit()
    service = RAGService(
        Settings(jwt_secret="x" * 32, openai_api_key="test-key"),
        FakeRetrieval(results), object(), FakeChats(), generator, audit, FakeMemory(),
    )
    user = User(id=uuid4(), email="admin@example.com", password_hash="x", role=Role.ADMIN,
                department_id=None, is_active=True, token_version=1)

    response = await service.ask(ChatRequest(question="What is the allowance?"), user)

    assert response.status == "insufficient_evidence"
    assert response.citations == []
    assert audit.events[0]["outcome"] == "contradictory_evidence"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("generated", "outcome"),
    [
        (GroundedAnswer(
            answer="Missing evidence", supported=False, contradictory=False,
            confidence=0.1, citation_ids=[], evidence_reason="Not present",
        ), "requested_information_missing"),
        (GroundedAnswer(
            answer="According to [S1], maybe.", supported=True, contradictory=False,
            confidence=0.2, citation_ids=["S1"],
        ), "insufficient_evidence"),
        (GroundedAnswer(
            answer="According to [S9], invalid.", supported=True, contradictory=False,
            confidence=0.9, citation_ids=["S9"],
        ), "invalid_citations"),
    ],
)
async def test_rag_fail_closed_generation_outcomes(generated, outcome):
    result = SearchResult(
        chunk="The trusted policy text.", score=0.9,
        metadata={"chunk_id": str(uuid4()), "filename": "Policy.pdf"},
        page_number=1, document_id=uuid4(),
    )
    audit = FakeAudit()
    service = RAGService(
        Settings(jwt_secret="x" * 32, openai_api_key="mock-openai-key"),
        FakeRetrieval([result]), object(), FakeChats(), FakeGenerator(generated), audit, FakeMemory(),
    )
    user = User(
        id=uuid4(), email="admin@example.com", password_hash="x", role=Role.ADMIN,
        department_id=None, is_active=True, token_version=1,
    )
    response = await service.ask(ChatRequest(question="What does the policy say?"), user)
    assert response.status == "insufficient_evidence"
    assert response.citations == []
    assert audit.events[0]["outcome"] == outcome
