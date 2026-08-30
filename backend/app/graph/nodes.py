import json
import logging
import os
import re
import time
from typing import Any

from app.graph.state import AgentState
from app.agents.router import AgentRouter
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.coding_agent import CodingAgent
from app.agents.vision_agent import VisionAgent
from app.agents.roadmap_agent import RoadmapAgent
from app.agents.diagnosis_agent import DiagnosisAgent
from app.services import memory_service
from app.services import embedding_service
from app.services.model_service import init_registry
from app.schemas.lightrag import QueryRequest
from app.tools import ToolRegistry

logger = logging.getLogger(__name__)

MAX_REFLECTION = 2

_router: AgentRouter | None = None


def _get_router() -> AgentRouter:
    global _router
    if _router is None:
        init_registry()
        _router = AgentRouter()
    return _router


def _now() -> float:
    import time
    return time.time()


def _is_expired(event: dict[str, Any]) -> bool:
    expired_at = event.get("expired_at")
    return bool(expired_at) and float(expired_at) <= _now()


def _dedup_facts(facts: list[str], limit: int = 20) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for fact in facts:
        normalized = " ".join(str(fact).split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            break
    return result


# 偏好类事实关键词（与下方 _PREF_KEYWORDS 同源，避免重复定义）
_PREF_KEYWORDS = {"喜欢", "不喜欢", "偏好", "倾向", "习惯", "偏爱", "prefer", "like", "dislike"}

# 语义去重 / 矛盾取代的余弦相似度阈值
_FACT_DEDUP_SIM = 0.92       # 高于此视为同一偏好，跳过（不再重复堆积）
_FACT_SUPERSEDE_SIM = 0.70   # 同一主题区间内，若情感极性相反则取代旧记录

# 负面情感 / 变更信号：用于判断新事实是否与旧事实相反（用户改口）
_NEG_SIGNALS = {
    "不", "没", "没有", "不再", "别", "讨厌", "反感", "烦", "厌恶", "嫌弃",
    "弃用", "放弃", "不用", "改", "换", "转", "dislike", "hate", "avoid",
    "stop", "no longer", "switched",
}


def _has_negative_signal(text: str) -> bool:
    """粗略判断文本是否含负面/变更情感信号。"""
    t = (text or "").lower()
    return any(tok in t for tok in _NEG_SIGNALS)


def _classify_fact_against_existing(
    fact: str,
    fact_emb: list[float] | None,
    active_facts: list[dict[str, Any]],
    dedup_sim: float = _FACT_DEDUP_SIM,
    supersede_sim: float = _FACT_SUPERSEDE_SIM,
) -> tuple[str, int | None]:
    """判断一条新事实相对已有活跃 fact 事件该如何处理。

    返回:
        ("skip", None)        —— 语义重复，已记录，跳过（避免堆积）
        ("supersede", old_id) —— 同一主题但情感相反，取代旧记录（调用方负责 expire）
        ("store", None)       —— 全新事实，正常落库
    无向量时退化为精确去重（由调用方用 normalize 比对），这里一律返回 store。
    """
    if fact_emb is None:
        return "store", None
    best_sim = 0.0
    best_old: dict[str, Any] | None = None
    for old in active_facts:
        emb = old.get("embedding")
        if emb is None:
            continue
        sim = embedding_service.cosine_similarity(fact_emb, emb)
        if sim > best_sim:
            best_sim = sim
            best_old = old
    if best_old is None:
        return "store", None

    is_pref = any(kw in fact for kw in _PREF_KEYWORDS) or any(
        kw in (best_old.get("content") or "") for kw in _PREF_KEYWORDS
    )
    opposite = _has_negative_signal(fact) != _has_negative_signal(best_old.get("content", ""))

    if best_sim >= dedup_sim:
        # 几乎同一句话：仅当是偏好且极性相反才取代，否则当作重复跳过
        if opposite and is_pref:
            return "supersede", best_old["id"]
        return "skip", None
    if best_sim >= supersede_sim and opposite and is_pref:
        return "supersede", best_old["id"]
    return "store", None


_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    """中文按字符 bigram、英文按单词切分。修复原先按空格 split 导致中文整句失效的问题。"""
    text = (text or "").lower()
    tokens: set[str] = set()
    for run in _CJK_RUN_RE.findall(text):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[i:i + 2] for i in range(len(run) - 1))
    for word in _WORD_RE.findall(text):
        if len(word) > 1:
            tokens.add(word)
    return tokens


def _time_decay(created_at: float, now_ts: float, half_life_days: float) -> float:
    age_days = max(0.0, (now_ts - float(created_at or now_ts)) / 86400.0)
    if half_life_days <= 0:
        return 1.0
    return 0.5 ** (age_days / half_life_days)


def _score_event(
    event: dict[str, Any],
    query_tokens: set[str],
    semantic_similarity: float | None,
    now_ts: float,
    half_life_days: float,
) -> float:
    """混合打分：语义余弦 0.55 + 关键词覆盖 0.25 + importance 0.1 + 时间衰减 0.1，反馈分作加成。

    无语义信号时（embedding 未配置/失败，或老事件缺向量），把 0.55 权重按比例还给其余部分，
    保证有向量和无向量的事件在同一尺度下竞争。
    """
    content_tokens = _tokenize(str(event.get("content", "")))
    importance = float(event.get("importance", 1.0) or 1.0)
    importance_term = min(1.0, importance / 2.0)
    decay = _time_decay(event.get("created_at"), now_ts, half_life_days)

    if not query_tokens:
        # 无查询词且无语义信号：没有依据区分相关性，整体不给分，避免 importance/decay 单独抬分
        if semantic_similarity is None:
            return 0.0
        keyword_part = 0.1 * importance_term + 0.1 * decay
        score = 0.55 * semantic_similarity + keyword_part
    else:
        coverage = len(query_tokens & content_tokens) / len(query_tokens)
        keyword_part = 0.25 * coverage + 0.1 * importance_term + 0.1 * decay
        if semantic_similarity is None:
            score = keyword_part / 0.45 if keyword_part > 0 else 0.0
        else:
            score = 0.55 * semantic_similarity + keyword_part

    feedback_count = float(event.get("feedback_count", 0) or 0)
    if feedback_count > 0:
        feedback_score = float(event.get("feedback_score", 0.0) or 0.0)
        score += 0.1 * (feedback_score / feedback_count)
    return max(0.0, min(1.0, score))


async def node_memory_retrieval(state: AgentState) -> dict[str, Any]:
    from app.config import settings

    session_id = state["session_id"]
    user_id = state.get("user_id", session_id)
    query = state.get("query", "")

    user_profile = await memory_service.get_user_profile(user_id)

    try:
        await memory_service.purge_expired_events(user_id)
    except Exception:
        pass

    candidates = await memory_service.get_memory_events_with_vectors(
        user_id, limit=100, min_importance=0.0
    )
    active_events = [event for event in candidates if not _is_expired(event)]

    query_embedding = await embedding_service.embed_text(query)
    query_tokens = _tokenize(query)
    now_ts = _now()
    half_life = settings.memory_decay_half_life_days

    scored_events = []
    for event in active_events:
        semantic_similarity: float | None = None
        if query_embedding is not None:
            vector = embedding_service.decode_vector(event.get("embedding"))
            if vector:
                semantic_similarity = max(0.0, min(1.0, embedding_service.cosine_similarity(query_embedding, vector)))
        score = _score_event(event, query_tokens, semantic_similarity, now_ts, half_life)
        scored_events.append({**event, "relevance_score": score})

    scored_events.sort(
        key=lambda item: (item.get("relevance_score", 0.0), item.get("importance", 0.0)),
        reverse=True,
    )
    ordered_events = scored_events[: settings.memory_semantic_top_k]
    for event in ordered_events:
        event.pop("embedding", None)

    conversation = await memory_service.get_memory(session_id, memory_type="conversation", limit=5)
    ordered_conversation = list(reversed(conversation))
    last_turn_context: dict[str, Any] = {}
    if ordered_conversation:
        last_turn = ordered_conversation[0]
        last_turn_context = {
            "last_user_message": (state.get("query") or "").strip(),
            "last_assistant_message": str(last_turn.get("content", "")),
            "last_turn_at": last_turn.get("created_at"),
        }

    return {
        "user_profile": user_profile,
        "memory_events": ordered_events,
        "last_turn_context": last_turn_context,
        "memory_context": {
            "conversation": ordered_conversation,
            "preferences": [],
        },
    }


async def node_router(state: AgentState) -> dict[str, Any]:
    router = _get_router()
    decision = await router.route(state["query"])
    return {
        "agent": decision.agent,
        "model": decision.model,
        "needs_rag": decision.needs_rag,
        "needs_memory": decision.needs_memory,
        "needs_tools": decision.needs_tools,
    }


async def node_knowledge_agent(state: AgentState) -> dict[str, Any]:
    agent = KnowledgeAgent(retrieval_mode="hybrid")
    try:
        result = await agent.run(state["query"], memory_context=state.get("memory_context", []), user_profile=state.get("user_profile"), memory_events=state.get("memory_events"))
    finally:
        await agent.close()
    return {
        "answer": result.answer,
        "sources": [
            {"file_path": s.file_path, "reference_id": s.reference_id}
            for s in result.sources
        ],
        "retrieval_mode": result.retrieval_mode,
        "latency": result.latency,
        "used_memories": result.used_memories,
    }


async def node_general_agent(state: AgentState) -> dict[str, Any]:
    from app.agents.general_agent import GeneralAgent
    
    agent = GeneralAgent()
    # 根据 needs_tools 决定是否提供工具
    tools = None
    if state.get("needs_tools", False):
        tools = ToolRegistry._tools.values()  # 获取所有已注册工具
    
    result = await agent.run(
        state["query"],
        memory_context=state.get("memory_context", []),
        user_profile=state.get("user_profile"),
        memory_events=state.get("memory_events"),
        tools=list(tools) if tools else None,
    )
    
    response = {
        "answer": result.answer,
        "sources": [
            {"file_path": s["file_path"], "reference_id": s["reference_id"]}
            if isinstance(s, dict) else {"file_path": s.file_path, "reference_id": s.reference_id}
            for s in result.sources
        ],
        "retrieval_mode": result.retrieval_mode,
        "latency": result.latency,
        "used_memories": result.used_memories,
    }

    # 如果有工具调用，添加到响应中
    if result.tool_calls:
        response["tool_calls"] = [
            {
                "name": tc.name,
                "arguments": tc.arguments,
                "result": tc.result,
                "error": tc.error,
                "latency": tc.latency,
            }
            for tc in result.tool_calls
        ]

    return response


async def node_reflection(state: AgentState) -> dict[str, Any]:
    answer = state.get("answer", "")
    count = state.get("reflection_count", 0)

    if not answer or len(answer) < 20:
        return {
            "reflection_passed": False,
            "reflection_notes": "Answer too short or empty",
            "reflection_count": count + 1,
        }

    if "I don't know" in answer or "No relevant context" in answer:
        return {
            "reflection_passed": False,
            "reflection_notes": "Answer indicates no knowledge found",
            "reflection_count": count + 1,
        }

    return {
        "reflection_passed": True,
        "reflection_notes": "OK",
        "reflection_count": count + 1,
    }


async def node_coding_agent(state: AgentState) -> dict[str, Any]:
    agent = CodingAgent()
    # 根据 needs_tools 决定是否提供工具
    tools = None
    if state.get("needs_tools", False):
        tools = ToolRegistry._tools.values()  # 获取所有已注册工具
    
    result = await agent.run(
        state["query"],
        memory_context=state.get("memory_context", []),
        user_profile=state.get("user_profile"),
        memory_events=state.get("memory_events"),
        tools=list(tools) if tools else None,
    )
    
    response = {
        "answer": result.answer,
        "sources": [
            {"file_path": s["file_path"], "reference_id": s["reference_id"]}
            if isinstance(s, dict) else {"file_path": s.file_path, "reference_id": s.reference_id}
            for s in result.sources
        ],
        "retrieval_mode": result.retrieval_mode,
        "latency": result.latency,
        "used_memories": result.used_memories,
    }

    # 如果有工具调用，添加到响应中
    if result.tool_calls:
        response["tool_calls"] = [
            {
                "name": tc.name,
                "arguments": tc.arguments,
                "result": tc.result,
                "error": tc.error,
                "latency": tc.latency,
            }
            for tc in result.tool_calls
        ]

    return response


async def node_vision_agent(state: AgentState) -> dict[str, Any]:
    agent = VisionAgent()
    result = await agent.run(state["query"], memory_context=state.get("memory_context", []), user_profile=state.get("user_profile"), memory_events=state.get("memory_events"))
    return {
        "answer": result.answer,
        "sources": [],
        "retrieval_mode": result.retrieval_mode,
        "latency": result.latency,
        "used_memories": getattr(result, "used_memories", []),
    }


async def node_roadmap_agent(state: AgentState) -> dict[str, Any]:
    user_id = state.get("user_id", state["session_id"])
    agent = RoadmapAgent()
    try:
        answer = await agent.run(state["query"], user_id=user_id)
    finally:
        await agent.close()
    return {"answer": answer, "sources": [], "retrieval_mode": "hybrid", "latency": 0.0}


async def node_diagnosis_agent(state: AgentState) -> dict[str, Any]:
    user_id = state.get("user_id", state["session_id"])
    agent = DiagnosisAgent()
    answer = await agent.run(user_id=user_id)
    return {"answer": answer, "sources": [], "retrieval_mode": "none", "latency": 0.0}


_EXTRACTION_PROMPT_TEMPLATE = """分析下面这段对话，提取用户表达的所有可长期使用的信息。

提取两类内容：

1. user_profile：结构化的个人属性（仅限以下字段）
   - name: 姓名
   - age: 年龄
   - gender: 性别
   - occupation: 职业/身份（如学生、工程师）
   - location: 所在地
   - goals: 学习/工作目标
   - constraints: 限制条件（时间、设备等）

2. facts：用户表达的所有偏好、习惯、倾向，每条一句话，包括但不限于：
   - 学习偏好（如：喜欢看代码示例、不喜欢长篇理论）
   - 风格偏好（如：喜欢简洁回答、偏好中文解释）
   - 技术偏好（如：偏好用 Python、不喜欢 Java）
   - 使用习惯（如：习惯边学边练）
   注意：只记录稳定的长期偏好，不记录临时性的一次性需求

只输出 JSON，不要解释：
{{"user_profile": {{}}, "facts": []}}
如无可记信息，返回上面的空结构。

对话：
User: {user_question}
Assistant: {assistant_answer}"""


def _parse_json_block(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


async def _extract_memory_signals(user_question: str, assistant_answer: str) -> tuple[dict[str, Any], list[str]]:
    """用轻量模型从对话中提取画像字段与偏好 facts；失败重试一次，仍失败则返回空结果。"""
    from openai import AsyncOpenAI
    from app.config import settings

    prompt = _EXTRACTION_PROMPT_TEMPLATE.format(user_question=user_question, assistant_answer=assistant_answer)
    llm = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            resp = await llm.chat.completions.create(
                model=settings.llm_model_light,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            data = _parse_json_block(resp.choices[0].message.content or "{}")
            profile_payload = data.get("user_profile") if isinstance(data.get("user_profile"), dict) else {}
            user_profile_update = {str(k): str(v) for k, v in profile_payload.items() if str(k) and str(v)}
            raw_facts = data.get("facts") if isinstance(data.get("facts"), list) else []
            facts = _dedup_facts([str(item) for item in raw_facts])
            return user_profile_update, facts
        except Exception as exc:
            last_error = exc
    logger.warning("memory extraction failed after retry: %s", last_error)
    return {}, []


async def _generate_profile_summary(profile: dict[str, Any]) -> str:
    """画像发生变化时用轻量模型生成真实摘要，失败返回空串（不写事件）。"""
    from openai import AsyncOpenAI
    from app.config import settings

    try:
        llm = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
        prompt = (
            "根据以下用户画像，用中文写一段 2-3 句话的简洁总结，概括这个用户的身份、目标和偏好，"
            "自然成文，不要逐条罗列字段：\n"
            + json.dumps(profile, ensure_ascii=False)
        )
        resp = await llm.chat.completions.create(
            model=settings.llm_model_light,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return (resp.choices[0].message.content or "").strip()[:300]
    except Exception as exc:
        logger.warning("profile summary generation failed: %s", exc)
        return ""


async def node_memory_update(state: AgentState) -> dict[str, Any]:
    import json

    answer = state.get("answer", "")
    session_id = state["session_id"]
    user_id = state.get("user_id", session_id)

    if answer and len(answer) > 50:
        await memory_service.save_memory(
            session=session_id,
            memory_type="conversation",
            content="Q: " + state["query"] + "\nA: " + answer[:1000],
        )

    user_question = (state.get("query") or "").strip()
    assistant_answer = (answer or "").strip()[:600]
    user_profile_update, facts = await _extract_memory_signals(user_question, assistant_answer)

    events: list[dict[str, Any]] = []
    existing_profile = await memory_service.get_user_profile(user_id)
    merged_profile = dict(existing_profile)
    changed_keys = {
        key: value
        for key, value in user_profile_update.items()
        if existing_profile.get(key) != value
    }

    if changed_keys:
        merged_profile.update(changed_keys)
        profile_update_events = []
        for key, value in changed_keys.items():
            profile_update_events.append({
                "event_type": "profile_update",
                "content": key + " -> " + value,
                "importance": 1.4,
                "source": "extraction",
                "confidence": 0.9,
                "metadata": {"previous_value": existing_profile[key]} if key in existing_profile else {},
            })
        events.extend(profile_update_events)
        # 画像 + profile_update 事件一次性写库
        await memory_service.save_structured_memory(
            user_id=user_id, profile=merged_profile, events=profile_update_events
        )

        summary_text = await _generate_profile_summary(merged_profile)
        if summary_text:
            summary_event = {
                "event_type": "profile_summary",
                "content": summary_text,
                "importance": 1.6,
                "source": "auto_summary",
                "metadata": {"keys": sorted(merged_profile.keys())},
            }
            # 旧摘要事件整体过期，事件流中任意时刻只有一条活跃摘要
            try:
                await memory_service.expire_events_of_type(user_id, "profile_summary")
            except Exception:
                pass
            merged_profile = {**merged_profile, "profile_summary": summary_text, "last_summary_at": _now()}
            await memory_service.save_structured_memory(user_id=user_id, profile=merged_profile, events=[summary_event])
            events.append(summary_event)

    if facts:
        existing_contents = await memory_service.find_existing_event_contents(user_id, facts)
        active_facts = await memory_service.get_active_fact_events(user_id)
        fact_embs = await embedding_service.embed_texts(facts)  # 无配置时返回 None
        fact_events = []
        superseded_ids: set[int] = set()
        for idx, fact in enumerate(facts):
            if memory_service.normalize_event_content(fact) in existing_contents:
                continue  # 精确去重：跨轮已存在相同 content 的 fact
            emb = fact_embs[idx] if fact_embs else None
            action, old_id = _classify_fact_against_existing(fact, emb, active_facts)
            if action == "skip":
                continue  # 语义重复：同一偏好已记录，跳过堆积
            if action == "supersede" and old_id is not None and old_id not in superseded_ids:
                await memory_service.expire_memory_event(user_id, old_id)
                superseded_ids.add(old_id)
            is_pref = any(kw in fact for kw in _PREF_KEYWORDS)
            fact_events.append({
                "event_type": "fact",
                "content": fact,
                "importance": 1.3 if is_pref else 1.0,
                "source": "extraction",
                "confidence": 0.9,
            })
        if fact_events:
            await memory_service.save_structured_memory(user_id=user_id, profile=None, events=fact_events)
            events.extend(fact_events)

    return {
        "user_profile": merged_profile,
        "memory_events": events,
        "last_turn_context": {},
    }
