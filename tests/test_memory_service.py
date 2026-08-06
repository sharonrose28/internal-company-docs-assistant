from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.user import Role
from app.services.memory import ConversationMemoryService


class FakeConversations:
    def __init__(self, messages):
        self.messages = messages
        self.requested_limit = None
        self.session = SimpleNamespace(id=uuid4(), title="Session")

    async def get_owned(self, session_id, _user_id):
        return self.session if session_id == self.session.id else None

    async def create(self, _user_id, _title):
        return self.session

    async def last_exchanges(self, _session_id, limit):
        self.requested_limit = limit
        return self.messages[-limit:]


class FakeDocuments:
    async def authorized_document_ids(self, _user, document_ids):
        return document_ids


@pytest.mark.asyncio
async def test_memory_requests_only_last_ten_exchanges():
    document_id = uuid4()
    messages = [SimpleNamespace(
        id=uuid4(), question=f"Question {index}", answer=f"Answer {index}",
        citations=[{"document_id": str(document_id)}],
    ) for index in range(12)]
    conversations = FakeConversations(messages)
    service = ConversationMemoryService(conversations, FakeDocuments())
    user = SimpleNamespace(id=uuid4(), role=Role.EMPLOYEE, department_id=uuid4())

    memory = await service.load(user, conversations.session.id, "Follow-up")

    assert conversations.requested_limit == 10
    assert len(memory.exchanges) == 10
    assert memory.exchanges[0].question == "Question 2"


@pytest.mark.asyncio
async def test_revoked_citations_remove_prior_answer_but_keep_question():
    document_id = uuid4()
    message = SimpleNamespace(
        id=uuid4(), question="What is the policy?", answer="Restricted answer",
        citations=[{"document_id": str(document_id)}],
    )
    conversations = FakeConversations([message])

    class NoAccess:
        async def authorized_document_ids(self, _user, _ids):
            return set()

    service = ConversationMemoryService(conversations, NoAccess())
    user = SimpleNamespace(id=uuid4(), role=Role.EMPLOYEE, department_id=uuid4())
    memory = await service.load(user, conversations.session.id, "Follow-up")
    assert memory.exchanges[0].question == "What is the policy?"
    assert memory.exchanges[0].answer is None

