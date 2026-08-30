import pytest
import sys
sys.path.insert(0, ".")

from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.knowledge_agent import KnowledgeAgent
from app.schemas.chat import KnowledgeAnswer
from app.schemas.lightrag import QueryResponse


def _make_rag_response(text: str):
    return QueryResponse(response=text, references=[])


def _make_llm_completion(text: str):
    choice = MagicMock()
    choice.message.content = text
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_knowledge_agent_uses_rag_response():
    agent = KnowledgeAgent()
    rag_text = "LangGraph 是一个基于图的 Agent 框架。"
    with patch.object(agent._lightrag, "query", new=AsyncMock(return_value=_make_rag_response(rag_text))), \
         patch.object(agent._llm.chat.completions, "create", new=AsyncMock(return_value=_make_llm_completion(rag_text))):
        result = await agent.run("什么是 LangGraph？")
    assert result.answer == rag_text
    assert isinstance(result, KnowledgeAnswer)
    assert result.latency >= 0


@pytest.mark.asyncio
async def test_knowledge_agent_fallback_on_empty_rag():
    agent = KnowledgeAgent()
    fallback_text = "我不知道这个问题的答案。"
    with patch.object(agent._lightrag, "query", new=AsyncMock(return_value=_make_rag_response(""))):
        with patch.object(agent._llm.chat.completions, "create", new=AsyncMock(return_value=_make_llm_completion(fallback_text))):
            result = await agent.run("一个不在知识库里的问题")
    assert result.answer == fallback_text


@pytest.mark.asyncio
async def test_knowledge_agent_fallback_on_no_context():
    agent = KnowledgeAgent()
    fallback_text = "通用回答内容"
    no_context = "No relevant context found for the query."
    with patch.object(agent._lightrag, "query", new=AsyncMock(return_value=_make_rag_response(no_context))):
        with patch.object(agent._llm.chat.completions, "create", new=AsyncMock(return_value=_make_llm_completion(fallback_text))):
            result = await agent.run("无关查询")
    assert result.answer == fallback_text


@pytest.mark.asyncio
async def test_knowledge_agent_handles_lightrag_unavailable():
    from app.services.lightrag_client import LightRAGUnavailableError
    agent = KnowledgeAgent()
    fallback_text = "降级回答"
    with patch.object(agent._lightrag, "query", new=AsyncMock(side_effect=LightRAGUnavailableError("down"))):
        with patch.object(agent._llm.chat.completions, "create", new=AsyncMock(return_value=_make_llm_completion(fallback_text))):
            result = await agent.run("某问题")
    assert result.answer == fallback_text


@pytest.mark.asyncio
async def test_knowledge_agent_answer_fields():
    agent = KnowledgeAgent()
    with patch.object(agent._lightrag, "query", new=AsyncMock(return_value=_make_rag_response("答案文本"))), \
         patch.object(agent._llm.chat.completions, "create", new=AsyncMock(return_value=_make_llm_completion("答案文本"))):
        result = await agent.run("问题")
    assert result.retrieval_mode == "hybrid"
    assert isinstance(result.model, str)
    assert isinstance(result.sources, list)


# --- _build_messages_with_memory (预算 + 溯源) ---

def test_build_messages_with_memory_returns_used_memories():
    from app.agents.knowledge_agent import _build_messages_with_memory
    events = [
        {"id": 1, "event_type": "fact", "content": "用户喜欢 Python", "relevance_score": 0.9},
        {"id": 2, "event_type": "fact", "content": "用户在北京工作", "relevance_score": 0.6},
    ]
    messages, used = _build_messages_with_memory(
        "问题", {"conversation": [], "preferences": []},
        user_profile={"name": "小明", "occupation": "学生"},
        memory_events=events,
    )
    assert len(used) == 2
    assert used[0]["id"] == 1
    assert "score" in used[0]
    # 系统消息包含画像与事件
    joined = "\n".join(m.get("content", "") for m in messages)
    assert "小明" in joined
    assert "用户喜欢 Python" in joined


def test_build_messages_respects_token_budget(monkeypatch):
    from unittest.mock import patch
    from app.agents import knowledge_agent as ka
    events = [{"id": i, "event_type": "fact", "content": "内容" * 200, "relevance_score": 0.9} for i in range(20)]
    with patch.object(ka.settings, "memory_context_budget_chars", 300):
        messages, used = ka._build_messages_with_memory(
            "问题", {"conversation": [], "preferences": []},
            user_profile={}, memory_events=events,
        )
    # 预算约束下只注入部分事件
    assert len(used) < len(events)
    joined = "\n".join(m.get("content", "") for m in messages)
    assert len(joined) <= 400  # 预算 + 事件列表开销的宽松上界


def test_build_messages_without_memory():
    from app.agents.knowledge_agent import _build_messages_with_memory
    messages, used = _build_messages_with_memory(
        "问题", {"conversation": [], "preferences": []}, user_profile={}, memory_events=[]
    )
    assert len(used) == 0
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "问题"
