import json
import pytest
import sys
sys.path.insert(0, ".")

from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.router import AgentRouter, RouterDecision, AGENT_TYPES


def _make_completion(content: str):
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_route_knowledge():
    router = AgentRouter()
    payload = json.dumps({"agent": "knowledge", "model": "x", "needs_rag": True, "needs_memory": False, "needs_tools": False})
    with patch.object(router._llm.chat.completions, "create", new=AsyncMock(return_value=_make_completion(payload))):
        decision = await router.route("什么是 LangGraph？")
    assert decision.agent == "knowledge"
    assert decision.needs_rag is True


@pytest.mark.asyncio
async def test_route_coding():
    router = AgentRouter()
    payload = json.dumps({"agent": "coding", "model": "x", "needs_rag": False, "needs_memory": False, "needs_tools": False})
    with patch.object(router._llm.chat.completions, "create", new=AsyncMock(return_value=_make_completion(payload))):
        decision = await router.route("帮我写一个快速排序")
    assert decision.agent == "coding"
    assert decision.needs_rag is False


@pytest.mark.asyncio
async def test_route_unknown_falls_back_to_general():
    router = AgentRouter()
    payload = json.dumps({"agent": "unknown_type", "model": "x", "needs_rag": False, "needs_memory": False, "needs_tools": False})
    with patch.object(router._llm.chat.completions, "create", new=AsyncMock(return_value=_make_completion(payload))):
        decision = await router.route("今天天气怎么样")
    assert decision.agent == "general"


@pytest.mark.asyncio
async def test_route_bad_json_falls_back():
    router = AgentRouter()
    with patch.object(router._llm.chat.completions, "create", new=AsyncMock(return_value=_make_completion("not json at all"))):
        decision = await router.route("随便问一句")
    assert decision.agent in AGENT_TYPES


@pytest.mark.asyncio
async def test_route_strips_markdown_code_fence():
    router = AgentRouter()
    payload = "```json\n" + json.dumps({"agent": "vision", "model": "x", "needs_rag": False, "needs_memory": False, "needs_tools": False}) + "\n```"
    with patch.object(router._llm.chat.completions, "create", new=AsyncMock(return_value=_make_completion(payload))):
        decision = await router.route("分析这张图片")
    assert decision.agent == "vision"


@pytest.mark.asyncio
async def test_decision_fields_present():
    router = AgentRouter()
    payload = json.dumps({"agent": "general", "model": "x", "needs_rag": False, "needs_memory": True, "needs_tools": False})
    with patch.object(router._llm.chat.completions, "create", new=AsyncMock(return_value=_make_completion(payload))):
        decision = await router.route("你好")
    assert isinstance(decision, RouterDecision)
    assert isinstance(decision.needs_memory, bool)
    assert isinstance(decision.needs_tools, bool)
    assert isinstance(decision.model, str) and decision.model


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "今天天气怎么样？",
    "现在最新的新闻有哪些",
    "查一下今天的股价",
    "实时汇率是多少",
])
async def test_time_sensitive_query_forces_tools(query):
    """实时类问题（天气/新闻/股价）即使 LLM 判 knowledge/no-tools 也要强制走 general + 工具"""
    router = AgentRouter()
    payload = json.dumps({"agent": "knowledge", "model": "x", "needs_rag": True, "needs_memory": False, "needs_tools": False})
    with patch.object(router._llm.chat.completions, "create", new=AsyncMock(return_value=_make_completion(payload))):
        decision = await router.route(query)
    assert decision.needs_tools is True
    assert decision.agent in ("general", "coding")


@pytest.mark.asyncio
async def test_normal_query_respects_llm_decision():
    """非实时问题不强制开工具，尊重 LLM 的判断"""
    router = AgentRouter()
    payload = json.dumps({"agent": "general", "model": "x", "needs_rag": False, "needs_memory": False, "needs_tools": False})
    with patch.object(router._llm.chat.completions, "create", new=AsyncMock(return_value=_make_completion(payload))):
        decision = await router.route("帮我解释一下什么是递归")
    assert decision.needs_tools is False


@pytest.mark.asyncio
@patch("app.agents.router._is_roadmap_query", return_value=True)
async def test_roadmap_keyword_overrides_llm(_mock):
    """即使 LLM 判为 knowledge，关键词命中后强制纠正为 roadmap"""
    router = AgentRouter()
    payload = json.dumps({"agent": "knowledge", "model": "x", "needs_rag": True, "needs_memory": False, "needs_tools": False})
    with patch.object(router._llm.chat.completions, "create", new=AsyncMock(return_value=_make_completion(payload))):
        decision = await router.route("帮我规划一下这本书的学习路线")
    assert decision.agent == "roadmap"


@pytest.mark.asyncio
@patch("app.agents.router._is_diagnosis_query", return_value=True)
async def test_diagnosis_keyword_overrides_llm(_mock):
    """即使 LLM 判为 general，关键词命中后强制纠正为 diagnosis"""
    router = AgentRouter()
    payload = json.dumps({"agent": "general", "model": "x", "needs_rag": False, "needs_memory": False, "needs_tools": False})
    with patch.object(router._llm.chat.completions, "create", new=AsyncMock(return_value=_make_completion(payload))):
        decision = await router.route("我学得怎么样了")
    assert decision.agent == "diagnosis"


@pytest.mark.asyncio
@patch("app.agents.router._is_roadmap_query", return_value=False)
@patch("app.agents.router._is_diagnosis_query", return_value=False)
async def test_no_keyword_fallback_respects_llm(_mock_rd, _mock_diag):
    """无关键词命中时完全尊重 LLM 判断"""
    router = AgentRouter()
    payload = json.dumps({"agent": "coding", "model": "x", "needs_rag": False, "needs_memory": False, "needs_tools": False})
    with patch.object(router._llm.chat.completions, "create", new=AsyncMock(return_value=_make_completion(payload))):
        decision = await router.route("写个快排")
    assert decision.agent == "coding"
