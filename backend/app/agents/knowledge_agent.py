import time
import os
from openai import AsyncOpenAI

from app.config import settings
from app.services.lightrag_client import LightRAGClient, LightRAGUnavailableError
from app.services.web_search import web_search
from app.schemas.lightrag import QueryRequest, SourceReference
from app.schemas.chat import KnowledgeAnswer


_KNOWLEDGE_SYSTEM_PROMPT = """你是一位 AI Agent 领域的专业学习助手。根据以下知识库检索结果回答用户问题。

要求：
1. 先准确回答用户问题，引用知识库内容作为依据，语言简洁专业
2. 回答结尾加一个「## 相关概念」章节，从知识库内容中找出 2~4 个与本问题密切相关的概念，说明它们与本问题的关联
   格式：`- **概念名**：与本问题的关联说明（一句话）`
3. 若知识库中没有足够相关内容，直接说明，不要编造

知识库检索结果：
{context}"""

_WEB_SEARCH_SYSTEM_PROMPT = """你是一位 AI Agent 领域的专业学习助手。根据以下网络搜索结果回答用户问题。

要求：
1. 基于搜索结果准确回答问题，语言简洁专业
2. 引用信息来源（网页标题）作为依据
3. 如果搜索结果不够充分，说明局限性

网络搜索结果：
{context}"""


def _build_messages_with_memory(query: str, memory_context, user_profile=None, memory_events=None) -> tuple[list, list[dict]]:
    """构建注入记忆的消息列表，返回 (messages, used_memories)。

    注入优先级：长期画像 -> 记忆事件（按相关性得分降序）-> 近期对话，
    总量受 MEMORY_CONTEXT_BUDGET_CHARS 约束，事件单条截断到 MEMORY_EVENT_SNIPPET_CHARS。
    used_memories 记录实际进入 prompt 的事件，用于前端溯源展示。
    """
    if isinstance(memory_context, dict):
        conversation = memory_context.get("conversation", [])
    else:
        conversation = memory_context or []

    parts: list[str] = []
    used_memories: list[dict] = []
    remaining = settings.memory_context_budget_chars

    def take(text: str) -> str | None:
        nonlocal remaining
        if remaining <= 0 or not text:
            return None
        clipped = text[:remaining]
        remaining -= len(clipped)
        return clipped

    if user_profile:
        profile_lines = "\n".join(
            f"{key}: {value}"
            for key, value in user_profile.items()
            if key and value and key != "last_summary_at"
        )
        clipped = take(profile_lines)
        if clipped:
            parts.append("[用户长期画像]\n" + clipped)

    if memory_events:
        event_lines = []
        snippet_limit = settings.memory_event_snippet_chars
        for event in memory_events:
            content = str(event.get("content", "")).strip()
            if not content:
                continue
            snippet = content[:snippet_limit]
            line = f"- {event.get('event_type', 'fact')}: {snippet}"
            if len(line) > remaining:
                break
            event_lines.append(line)
            used_memories.append({
                "id": event.get("id"),
                "event_type": event.get("event_type", "fact"),
                "content": snippet[:120],
                "score": round(float(event.get("relevance_score", 0.0) or 0.0), 3),
            })
            remaining -= len(line)
        if event_lines:
            parts.append("[相关记忆事件]\n" + "\n".join(event_lines))

    if conversation:
        conv_lines = "\n".join(
            m.get("content", "") if isinstance(m, dict) else str(m)
            for m in conversation
        )
        clipped = take(conv_lines)
        if clipped:
            parts.append("[近期对话历史]\n" + clipped)

    messages = []
    if parts:
        messages.append({
            "role": "system",
            "content": "\n\n".join(parts),
        })

    messages.append({"role": "user", "content": query})
    return messages, used_memories
class KnowledgeAgent:
    def __init__(self, retrieval_mode: str = "hybrid") -> None:
        self._retrieval_mode = retrieval_mode
        self._lightrag = LightRAGClient()
        self._llm = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
        self._model = settings.llm_model_main

    async def run(self, query: str, memory_context: list = [], user_profile=None, memory_events=None) -> KnowledgeAnswer:
        start = time.monotonic()

        # 1. 检索：only_need_context=True 获取原始知识块，由我们的 LLM 做增强回答
        try:
            rag_response = await self._lightrag.query(
                QueryRequest(query=query, mode=self._retrieval_mode, only_need_context=True)
            )
            context = rag_response.response
            sources = rag_response.references
        except LightRAGUnavailableError:
            context = ""
            sources = []

        # 2. 有知识库内容 → 用主力 LLM 做增强回答（含相关概念关联）
        if context and context != "No relevant context found for the query.":
            system_content = _KNOWLEDGE_SYSTEM_PROMPT.format(context=context[:4000])
            messages, used_memories = _build_messages_with_memory(
                query, memory_context,
                user_profile=user_profile,
                memory_events=memory_events,
            )
            messages.insert(0, {"role": "system", "content": system_content})
            completion = await self._llm.chat.completions.create(
                model=self._model,
                messages=messages,
            )
            answer_text = completion.choices[0].message.content or ""
            retrieval_mode = self._retrieval_mode

        else:
            # 3. 知识库无内容 → 尝试 web search
            web_results = await web_search(query, max_results=5)

            if web_results:
                # 把搜索结果格式化为 context
                web_context = "\n\n".join(
                    f"【{r['title']}】({r['url']})\n{r['snippet']}"
                    for r in web_results
                    if r.get("snippet")
                )
                system_content = _WEB_SEARCH_SYSTEM_PROMPT.format(context=web_context[:4000])
                messages, used_memories = _build_messages_with_memory(
                    query, memory_context,
                    user_profile=user_profile,
                    memory_events=memory_events,
                )
                messages.insert(0, {"role": "system", "content": system_content})
                completion = await self._llm.chat.completions.create(
                    model=self._model,
                    messages=messages,
                )
                answer_text = completion.choices[0].message.content or ""
                # web search 来源
                sources = [
                    SourceReference(
                        reference_id=f"web_{i}",
                        file_path=r["url"],
                        content=r["title"],
                    )
                    for i, r in enumerate(web_results)
                ]
                retrieval_mode = "web"
            else:
                # 4. web search 也没结果 → 纯 LLM 回退
                messages, used_memories = _build_messages_with_memory(
                    query, memory_context,
                    user_profile=user_profile,
                    memory_events=memory_events,
                )
                completion = await self._llm.chat.completions.create(
                    model=self._model,
                    messages=messages,
                )
                answer_text = completion.choices[0].message.content or ""
                retrieval_mode = "none"

        latency = time.monotonic() - start
        return KnowledgeAnswer(
            answer=answer_text,
            sources=sources,
            retrieval_mode=retrieval_mode,
            latency=round(latency, 3),
            model=self._model,
            used_memories=used_memories,
        )

    async def close(self) -> None:
        await self._lightrag.release()
