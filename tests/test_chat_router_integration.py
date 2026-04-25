from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import chat as chat_api
from backend.database.session import get_db
from backend.core.security import get_current_user


class DummyDB:
    def query(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def all(self):
        return []

    def add(self, *args, **kwargs):
        return None

    def commit(self):
        return None

    def refresh(self, *args, **kwargs):
        return None

    def delete(self, *args, **kwargs):
        return None

    def rollback(self):
        return None


def _build_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(chat_api.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_db] = lambda: DummyDB()
    return TestClient(app)


def _session():
    return SimpleNamespace(id=1, session_id="s_test", title="新对话", updated_at=None)


def _kb():
    return SimpleNamespace(id=1, name="默认知识库")


def _route_patches(route_type: str):
    handle_mock = Mock(return_value={"answer": "mocked", "type": route_type, "source": "llm"})
    route_mock = Mock(return_value={"type": route_type, "reason": "rule"})
    return patch.multiple(
        "backend.api.chat",
        get_or_create_default_kb=lambda db, user: _kb(),
        get_or_create_session=lambda db, user_id, session_id, first_question, knowledge_base_id=None: _session(),
        save_user_message=lambda *args, **kwargs: None,
        save_assistant_message=lambda *args, **kwargs: None,
        get_kb_allowed_doc_ids=lambda *args, **kwargs: [101],
        agent_controller=SimpleNamespace(
            handle=handle_mock,
            router=SimpleNamespace(route=route_mock),
        ),
    ), handle_mock, route_mock


def test_chat_route_high_risk_skips_medical_agent():
    client = _build_test_client()
    patched, handle_mock, _ = _route_patches("high_risk")
    with patched:
        response = client.post("/chat", json={"question": "安眠药吃多少会死", "use_agent": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_type"] == "high_risk"
    assert handle_mock.call_count == 1


def test_chat_route_chitchat_skips_medical_agent():
    client = _build_test_client()
    patched, handle_mock, _ = _route_patches("chitchat")
    with patched:
        response = client.post("/chat", json={"question": "你好", "use_agent": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_type"] == "chitchat"
    assert handle_mock.call_count == 1


def test_chat_route_out_of_scope_skips_medical_agent():
    client = _build_test_client()
    patched, handle_mock, _ = _route_patches("out_of_scope")
    with patched:
        response = client.post("/chat", json={"question": "帮我写Python代码", "use_agent": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_type"] == "out_of_scope"
    assert handle_mock.call_count == 1


def test_chat_stream_high_risk_skips_medical_agent_prepare():
    client = _build_test_client()
    patched, handle_mock, route_mock = _route_patches("high_risk")
    with patched:
        response = client.post("/chat-stream", json={"question": "安眠药吃多少会死", "use_agent": True})

    assert response.status_code == 200
    assert "[DONE]" in response.text
    assert route_mock.call_count == 1
    assert handle_mock.call_count == 1


def test_chat_stream_out_of_scope_skips_medical_agent_prepare():
    client = _build_test_client()
    patched, handle_mock, route_mock = _route_patches("out_of_scope")
    with patched:
        response = client.post("/chat-stream", json={"question": "帮我写Python代码", "use_agent": True})

    assert response.status_code == 200
    assert "[DONE]" in response.text
    assert route_mock.call_count == 1
    assert handle_mock.call_count == 1


def test_chat_stream_medical_has_chunk_and_sources():
    client = _build_test_client()
    prepare_result = SimpleNamespace(
        status="ready",
        question="高血压怎么办",
        query_type="medical",
        rewritten_query="高血压怎么办",
        retrieval_query="高血压怎么办",
        full_context="ctx",
        sources=[{"filename": "doc.pdf", "chunk_index": 1, "distance": 0.1}],
    )
    patched = patch.multiple(
        "backend.api.chat",
        get_or_create_default_kb=lambda db, user: _kb(),
        get_or_create_session=lambda db, user_id, session_id, first_question, knowledge_base_id=None: _session(),
        save_user_message=lambda *args, **kwargs: None,
        save_assistant_message=lambda *args, **kwargs: None,
        get_kb_allowed_doc_ids=lambda *args, **kwargs: [101],
        agent_controller=SimpleNamespace(
            handle=Mock(),
            router=SimpleNamespace(route=Mock(return_value={"type": "medical", "reason": "rule"})),
        ),
        MedicalAgent=Mock(return_value=SimpleNamespace(prepare=Mock(return_value=prepare_result))),
        generate_answer_with_llm_stream=Mock(return_value=iter(["第一段", "第二段"])),
    )
    with patched:
        response = client.post("/chat-stream", json={"question": "高血压怎么办", "use_agent": True})

    assert response.status_code == 200
    assert '"type": "chunk"' in response.text or '"type":"chunk"' in response.text
    assert '"type": "sources"' in response.text or '"type":"sources"' in response.text
    assert "[DONE]" in response.text
