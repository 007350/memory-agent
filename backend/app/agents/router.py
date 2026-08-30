import json
import os
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.config import settings
from app.services.model_registry import ModelRegistry, ModelCapability


_AGENT_TYPES = ("knowledge", "coding", "vision", "general", "roadmap", "diagnosis")
AGENT_TYPES = _AGENT_TYPES

# 时间敏感/实时类问题的关键词：知识库无法覆盖，强制启用工具（web_search）
_TIME_SENSITIVE_KEYWORDS = (
    "天气", "气温", "温度多少", "今天多少度",
    "新闻", "最新", "最新版", "实时", "现在", "目前", "当前",
    "股价", "汇率", "今天有", "今天出",
    "weather", "forecast", "news", "latest", "stock price", "exchange rate",
)

# 学习路线规划关键词：LLM 轻量模型容易漏判，用关键词兜底
_ROADMAP_KEYWORDS = (
    "学习路线", "学习计划", "学习路径", "学习规划", "学习方案",
    "roadmap", "study plan", "study path",
    "规划.*学习", "制定.*学习", "生成.*路线",
    "帮我规划", "帮我制定", "帮我生成.*路线", "帮我安排.*学习",
)

# 学习诊断关键词
_DIAGNOSIS_KEYWORDS = (
    "学习诊断", "学习报告", "进度报告", "学得怎么样", "学了多少",
    "我学得如何", "我的进度", "学习分析", "掌握情况",
    "diagnosis", "progress report", "how am i doing", "what have i learned",
)


def _needs_tools_hint(query: str) -> bool:
    return any(kw in query for kw in _TIME_SENSITIVE_KEYWORDS)


def _is_roadmap_query(query: str) -> bool:
    import re
    return any(re.search(kw, query) for kw in _ROADMAP_KEYWORDS)


def _is_diagnosis_query(query: str) -> bool:
    import re
    return any(re.search(kw, query) for kw in _DIAGNOSIS_KEYWORDS)

_SYSTEM_PROMPT = """You are a routing agent. Given a user query, determine the most suitable agent.

Agents:
- knowledge: questions requiring factual lookup, document retrieval, concept explanation, RAG
- coding: code generation, debugging, code review, programming help
- vision: image analysis, multimodal tasks (requires image input)
- roadmap: user wants to generate or review a learning roadmap / study plan for a document or topic
- diagnosis: user wants a learning diagnosis, progress report, study analysis, or asks "how am I doing" / "what have I learned"
- general: small talk, simple questions, anything that doesn't fit the above

Also determine:
- needs_rag: true if a knowledge base lookup would help answer the question
- needs_memory: true if prior conversation context is important
- needs_tools: true if external tools (search, calculator, etc.) are needed

Respond ONLY with valid JSON, no markdown, no commentary:
{"agent": "<agent>", "model": "<model_name>", "needs_rag": <bool>, "needs_memory": <bool>, "needs_tools": <bool>}
"""


@dataclass
class RouterDecision:
    agent: str
    model: str
    needs_rag: bool
    needs_memory: bool
    needs_tools: bool


class AgentRouter:
    def __init__(self) -> None:
        self._llm = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
        # 路由本身用轻量模型
        self._model = settings.llm_model_light

    async def route(self, query: str) -> RouterDecision:
        completion = await self._llm.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0,
        )
        raw = completion.choices[0].message.content or "{}"

        # 兼容模型在 JSON 外包裹 ```json ... ``` 的情况
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        agent = data.get("agent", "general")
        if agent not in _AGENT_TYPES:
            agent = "general"

        # model 字段取注册表默认，不信任模型自填写的名字（防止幻觉）
        try:
            model = ModelRegistry.default().name
        except RuntimeError:
            model = settings.llm_model_main

        # 实时类问题（天气/新闻/股价等）静态知识库答不了：强制启用工具，
        # 且不走 knowledge agent（它没有工具能力），改由 general agent 带 web_search 处理
        if _needs_tools_hint(query):
            needs_tools = True
            if agent not in ("general", "coding"):
                agent = "general"
        else:
            needs_tools = bool(data.get("needs_tools", agent == "knowledge"))

        # 学习路线/诊断请求的兜底：轻量模型容易漏判，关键词命中后强制纠正
        if _is_roadmap_query(query):
            agent = "roadmap"
        elif _is_diagnosis_query(query):
            agent = "diagnosis"

        return RouterDecision(
            agent=agent,
            model=model,
            needs_rag=bool(data.get("needs_rag", agent == "knowledge")),
            needs_memory=bool(data.get("needs_memory", False)),
            needs_tools=needs_tools,
        )
