"""Roadmap Agent 测试

重点覆盖一处历史 bug：提示词模板里含 JSON 示例（{"doc_name": ...}），
花括号未转义时会被 str.format() 当作占位符解析，抛 KeyError: '"doc_name"'，
且该行原本位于 try 块之外，异常直接冒泡导致 /chat 返回 500。
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.roadmap_agent import (
    _EXTRACT_PROMPT,
    _STEPS_PROMPT,
    RoadmapAgent,
)


def _make_completion(content: str) -> MagicMock:
    comp = MagicMock()
    comp.choices = [MagicMock()]
    comp.choices[0].message.content = content
    return comp


# --------------------------------------------------------------------------
# 回归测试：提示词模板渲染（花括号必须转义）
# --------------------------------------------------------------------------

def test_extract_prompt_renders_without_keyerror():
    """_EXTRACT_PROMPT 含 JSON 示例，花括号必须写成 {{ }}"""
    rendered = _EXTRACT_PROMPT.format(query="帮我规划 LangGraph 的学习路线")
    assert "帮我规划 LangGraph 的学习路线" in rendered
    # JSON 示例必须原样保留在提示词里，而不是被 format 当成字段替换掉
    assert '"doc_name"' in rendered


def test_steps_prompt_renders_without_keyerror():
    """_STEPS_PROMPT 同理，含 JSON 数组示例"""
    rendered = _STEPS_PROMPT.format(context="一些文档内容")
    assert "一些文档内容" in rendered
    assert '"title"' in rendered


# --------------------------------------------------------------------------
# _extract_doc_name
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_doc_name_parses_llm_json():
    agent = RoadmapAgent()
    payload = '{"doc_name": "LangGraph"}'
    with patch.object(
        agent._llm.chat.completions,
        "create",
        new=AsyncMock(return_value=_make_completion(payload)),
    ):
        name = await agent._extract_doc_name("帮我规划 LangGraph 的学习路线")
    assert name == "LangGraph"


@pytest.mark.asyncio
async def test_extract_doc_name_handles_markdown_fence():
    agent = RoadmapAgent()
    payload = '```json\n{"doc_name": "LightRAG"}\n```'
    with patch.object(
        agent._llm.chat.completions,
        "create",
        new=AsyncMock(return_value=_make_completion(payload)),
    ):
        name = await agent._extract_doc_name("帮我规划 LightRAG 的学习路线")
    assert name == "LightRAG"


@pytest.mark.asyncio
async def test_extract_doc_name_returns_empty_on_llm_error():
    """LLM 异常时降级为空串，不应把异常抛给上层（历史上会导致 500）"""
    agent = RoadmapAgent()
    with patch.object(
        agent._llm.chat.completions,
        "create",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        name = await agent._extract_doc_name("随便一句话")
    assert name == ""


@pytest.mark.asyncio
async def test_extract_doc_name_returns_empty_on_empty_field():
    agent = RoadmapAgent()
    payload = '{"doc_name": ""}'
    with patch.object(
        agent._llm.chat.completions,
        "create",
        new=AsyncMock(return_value=_make_completion(payload)),
    ):
        name = await agent._extract_doc_name("帮我规划一下这本书的学习路线")
    assert name == ""


# --------------------------------------------------------------------------
# _generate_steps
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_steps_validates_and_renumbers():
    agent = RoadmapAgent()
    payload = (
        '[{"title": "第一步", "detail": "内容A"},'
        ' {"detail": "缺标题应被丢弃"},'
        ' {"title": "第二步", "detail": "内容B"}]'
    )
    with patch.object(
        agent._llm.chat.completions,
        "create",
        new=AsyncMock(return_value=_make_completion(payload)),
    ):
        steps = await agent._generate_steps("context")
    # 缺 title 的条目被丢弃，保留的重新编号
    assert len(steps) == 2
    assert [s["id"] for s in steps] == [1, 2]
    assert steps[0]["title"] == "第一步"
    assert steps[1]["title"] == "第二步"
    assert all(s["done"] is False for s in steps)


@pytest.mark.asyncio
async def test_generate_steps_returns_empty_on_invalid_json():
    agent = RoadmapAgent()
    with patch.object(
        agent._llm.chat.completions,
        "create",
        new=AsyncMock(return_value=_make_completion("not json at all")),
    ):
        steps = await agent._generate_steps("context")
    assert steps == []
