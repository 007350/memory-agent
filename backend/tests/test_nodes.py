import json
import os
import time

import pytest
import sys
sys.path.insert(0, ".")

from unittest.mock import AsyncMock, patch

from app.services import memory_service
from app.services import embedding_service
from app.graph.nodes import (
    node_reflection,
    node_memory_retrieval,
    node_memory_update,
    _is_expired,
    _dedup_facts,
    _tokenize,
    _score_event,
    _parse_json_block,
    _classify_fact_against_existing,
    _has_negative_signal,
    _FACT_DEDUP_SIM,
    _FACT_SUPERSEDE_SIM,
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch, tmp_path):
    """独立临时数据库 + 关闭 embedding（避免测试触网）。"""
    db_file = tmp_path / "test_nodes.db"
    monkeypatch.setenv("MEMORY_DB_PATH", str(db_file))
    monkeypatch.setattr(embedding_service, "is_available", lambda: False)


# --- _is_expired ---

def test_is_expired_no_field():
    assert _is_expired({}) is False


def test_is_expired_future():
    assert _is_expired({"expired_at": time.time() + 3600}) is False


def test_is_expired_past():
    assert _is_expired({"expired_at": time.time() - 1}) is True


# --- _dedup_facts ---

def test_dedup_removes_duplicates():
    facts = ["learn Python", "learn Python", "use LangGraph"]
    result = _dedup_facts(facts)
    assert result == ["learn Python", "use LangGraph"]


def test_dedup_limit():
    facts = [f"fact {i}" for i in range(30)]
    result = _dedup_facts(facts, limit=5)
    assert len(result) == 5


def test_dedup_skips_empty():
    facts = ["", "  ", "real fact"]
    result = _dedup_facts(facts)
    assert result == ["real fact"]


# --- _tokenize ---

def test_tokenize_chinese_bigrams():
    tokens = _tokenize("我喜欢Python")
    # 中文按字符 bigram 切分
    assert "喜欢" in tokens
    assert "我喜" in tokens
    # 英文按单词切分并转小写
    assert "python" in tokens


def test_tokenize_english_words():
    tokens = _tokenize("LangGraph is great")
    assert "langgraph" in tokens
    assert "great" in tokens


def test_tokenize_empty():
    assert _tokenize("") == set()
    assert _tokenize(None) == set()


# --- _score_event ---

def test_score_event_zero_on_no_signal():
    now = time.time()
    event = {"content": "completely unrelated", "importance": 1.0, "created_at": now}
    score = _score_event(event, set(), None, now, 14)
    assert score == 0.0


def test_score_event_increases_with_keyword_match():
    now = time.time()
    event = {"content": "用户喜欢 Python", "importance": 1.0, "created_at": now}
    score_match = _score_event(event, _tokenize("用户喜欢 Python"), None, now, 14)
    score_no_match = _score_event(event, _tokenize("完全无关的查询内容"), None, now, 14)
    assert score_match > score_no_match


def test_score_event_semantic_increases_score():
    now = time.time()
    event = {"content": "用户喜欢 Python", "importance": 1.0, "created_at": now}
    tokens = _tokenize("用户喜欢 Python")
    low = _score_event(event, tokens, 0.1, now, 14)
    high = _score_event(event, tokens, 0.9, now, 14)
    assert high > low


def test_score_event_time_decay():
    now = time.time()
    event = {"content": "用户喜欢 Python", "importance": 1.0}
    tokens = _tokenize("用户喜欢 Python")
    fresh = _score_event(event, tokens, None, now, 14)
    stale = _score_event({**event, "created_at": now - 365 * 86400}, tokens, None, now, 14)
    assert fresh > stale


def test_score_event_feedback_bonus():
    now = time.time()
    event = {"content": "用户喜欢 Python", "importance": 1.0, "created_at": now}
    tokens = _tokenize("用户喜欢 Python")
    base = _score_event(event, tokens, None, now, 14)
    upvoted = _score_event(
        {**event, "feedback_count": 2, "feedback_score": 2.0}, tokens, None, now, 14
    )
    assert upvoted > base


def test_score_event_bounded():
    now = time.time()
    event = {"content": "用户喜欢 Python", "importance": 2.0, "created_at": now,
             "feedback_count": 5, "feedback_score": 5.0}
    score = _score_event(event, _tokenize("用户喜欢 Python"), 1.0, now, 14)
    assert 0.0 <= score <= 1.0


# --- _parse_json_block ---

def test_parse_json_block_plain():
    assert _parse_json_block('{"a": 1}') == {"a": 1}


def test_parse_json_block_with_fence():
    assert _parse_json_block('```json\n{"a": 1}\n```') == {"a": 1}


# --- node_reflection ---

@pytest.mark.asyncio
async def test_reflection_passes_good_answer():
    state = {"answer": "这是一段超过二十字的答案内容，足够长且不含无效标记。", "reflection_count": 0}
    result = await node_reflection(state)
    assert result["reflection_passed"] is True
    assert result["reflection_count"] == 1


@pytest.mark.asyncio
async def test_reflection_fails_short_answer():
    state = {"answer": "短", "reflection_count": 0}
    result = await node_reflection(state)
    assert result["reflection_passed"] is False


@pytest.mark.asyncio
async def test_reflection_fails_no_knowledge():
    state = {"answer": "No relevant context found in knowledge base.", "reflection_count": 0}
    result = await node_reflection(state)
    assert result["reflection_passed"] is False


@pytest.mark.asyncio
async def test_reflection_increments_count():
    state = {"answer": "这是足够长的答案内容以便通过 reflection 检查，不含无效词。", "reflection_count": 2}
    result = await node_reflection(state)
    assert result["reflection_count"] == 3


# --- node_memory_retrieval (mocked) ---

@pytest.mark.asyncio
async def test_node_memory_retrieval_structure():
    state = {"session_id": "s1", "user_id": "u1", "query": "LangGraph 是什么"}
    profile = {"name": "Alice"}
    events = [{"id": 1, "content": "LangGraph event", "importance": 1.0, "created_at": time.time()}]
    conversation = [{"content": "previous msg", "created_at": 123}]

    with patch("app.graph.nodes.memory_service") as mock_svc, \
         patch("app.graph.nodes.embedding_service") as mock_emb:
        mock_svc.get_user_profile = AsyncMock(return_value=profile)
        mock_svc.get_memory_events_with_vectors = AsyncMock(return_value=events)
        mock_svc.purge_expired_events = AsyncMock(return_value=0)
        mock_svc.get_memory = AsyncMock(return_value=conversation)
        mock_emb.embed_text = AsyncMock(return_value=None)
        result = await node_memory_retrieval(state)

    assert result["user_profile"] == profile
    assert len(result["memory_events"]) == 1
    assert result["memory_events"][0]["relevance_score"] > 0
    assert isinstance(result["memory_context"]["conversation"], list)


@pytest.mark.asyncio
async def test_node_memory_retrieval_prefers_matching_event():
    """中文查询下，关键词命中的事件应排在未命中的前面。"""
    state = {"session_id": "s1", "user_id": "u1", "query": "我喜欢什么编程语言"}
    now = time.time()
    events = [
        {"id": 1, "content": "用户喜欢 Python", "importance": 1.0, "created_at": now},
        {"id": 2, "content": "用户在北京工作", "importance": 1.0, "created_at": now},
    ]

    with patch("app.graph.nodes.memory_service") as mock_svc, \
         patch("app.graph.nodes.embedding_service") as mock_emb:
        mock_svc.get_user_profile = AsyncMock(return_value={})
        mock_svc.get_memory_events_with_vectors = AsyncMock(return_value=events)
        mock_svc.purge_expired_events = AsyncMock(return_value=0)
        mock_svc.get_memory = AsyncMock(return_value=[])
        mock_emb.embed_text = AsyncMock(return_value=None)
        result = await node_memory_retrieval(state)

    ordered = result["memory_events"]
    assert ordered[0]["content"] == "用户喜欢 Python"


@pytest.mark.asyncio
async def test_node_memory_retrieval_excludes_expired():
    now = time.time()
    events = [
        {"id": 1, "content": "用户喜欢 Python", "importance": 1.0, "created_at": now},
        {"id": 2, "content": "旧目标", "importance": 1.0, "created_at": now, "expired_at": now - 10},
    ]

    with patch("app.graph.nodes.memory_service") as mock_svc, \
         patch("app.graph.nodes.embedding_service") as mock_emb:
        mock_svc.get_user_profile = AsyncMock(return_value={})
        mock_svc.get_memory_events_with_vectors = AsyncMock(return_value=events)
        mock_svc.purge_expired_events = AsyncMock(return_value=0)
        mock_svc.get_memory = AsyncMock(return_value=[])
        mock_emb.embed_text = AsyncMock(return_value=None)
        result = await node_memory_retrieval({"session_id": "s1", "user_id": "u1", "query": "偏好"})

    contents = [e["content"] for e in result["memory_events"]]
    assert contents == ["用户喜欢 Python"]


# --- node_memory_update ---

def _update_state(user_id: str, session_id: str = "s1", answer: str = "好的，我会注意保持回答简洁，" + "详细内容" * 30) -> dict:
    return {"query": "我叫小明，喜欢简洁的回答", "answer": answer, "session_id": session_id, "user_id": user_id}


@pytest.mark.asyncio
async def test_memory_update_extracts_profile_and_facts():
    signals = ({"name": "小明", "occupation": "学生"}, ["喜欢简洁回答"])
    with patch("app.graph.nodes._extract_memory_signals", AsyncMock(return_value=signals)), \
         patch("app.graph.nodes._generate_profile_summary", AsyncMock(return_value="小明是学生，喜欢简洁回答")):
        result = await node_memory_update(_update_state("u1"))

    profile = await memory_service.get_user_profile("u1")
    assert profile["name"] == "小明"
    assert profile["occupation"] == "学生"
    assert profile["profile_summary"] == "小明是学生，喜欢简洁回答"

    events = await memory_service.get_memory_events("u1", limit=50)
    types = [e["event_type"] for e in events]
    assert types.count("profile_update") == 2
    assert types.count("fact") == 1
    assert types.count("profile_summary") == 1

    conversation = await memory_service.get_memory("s1", memory_type="conversation")
    assert len(conversation) == 1
    assert conversation[0]["content"].startswith("Q: 我叫小明")


@pytest.mark.asyncio
async def test_memory_update_dedups_facts_across_turns():
    signals = ({"name": "小明"}, ["喜欢简洁回答"])
    with patch("app.graph.nodes._extract_memory_signals", AsyncMock(return_value=signals)), \
         patch("app.graph.nodes._generate_profile_summary", AsyncMock(return_value="摘要")):
        await node_memory_update(_update_state("u2"))
        # 第二轮提取出完全相同的 fact 与画像 → 不应重复入库
        result = await node_memory_update(_update_state("u2"))

    events = await memory_service.get_memory_events("u2", limit=100)
    assert len([e for e in events if e["event_type"] == "fact"]) == 1
    # 画像未变化 → 不产生新的 summary 事件
    assert len([e for e in events if e["event_type"] == "profile_summary"]) == 1
    assert result["user_profile"].get("name") == "小明"


@pytest.mark.asyncio
async def test_memory_update_replaces_old_summary():
    with patch("app.graph.nodes._extract_memory_signals", AsyncMock(return_value=({"name": "小明"}, []))), \
         patch("app.graph.nodes._generate_profile_summary", AsyncMock(return_value="第一版摘要")):
        await node_memory_update(_update_state("u3"))

    with patch("app.graph.nodes._extract_memory_signals", AsyncMock(return_value=({"occupation": "工程师"}, []))), \
         patch("app.graph.nodes._generate_profile_summary", AsyncMock(return_value="第二版摘要")):
        await node_memory_update(_update_state("u3"))

    events = await memory_service.get_memory_events("u3", limit=100)
    active_summaries = [e for e in events if e["event_type"] == "profile_summary" and not e["expired_at"]]
    assert len(active_summaries) == 1
    assert active_summaries[0]["content"] == "第二版摘要"
    # 旧摘要事件被标记过期而非删除
    assert any(e["event_type"] == "profile_summary" and e["expired_at"] for e in events)


@pytest.mark.asyncio
async def test_memory_update_records_previous_value():
    with patch("app.graph.nodes._extract_memory_signals", AsyncMock(return_value=({"occupation": "学生"}, []))), \
         patch("app.graph.nodes._generate_profile_summary", AsyncMock(return_value="摘要一")):
        await node_memory_update(_update_state("u4"))

    with patch("app.graph.nodes._extract_memory_signals", AsyncMock(return_value=({"occupation": "工程师"}, []))), \
         patch("app.graph.nodes._generate_profile_summary", AsyncMock(return_value="摘要二")):
        await node_memory_update(_update_state("u4"))

    events = await memory_service.get_memory_events("u4", limit=100)
    updates = [e for e in events if e["event_type"] == "profile_update"]
    assert len(updates) == 2
    changed = [e for e in updates if e["content"].startswith("occupation -> 工程师")]
    assert len(changed) == 1
    metadata = changed[0]["metadata"]
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    assert metadata.get("previous_value") == "学生"


@pytest.mark.asyncio
async def test_memory_update_extraction_failure_is_safe():
    with patch("app.graph.nodes._extract_memory_signals", AsyncMock(return_value=({}, []))):
        result = await node_memory_update(_update_state("u5"))

    assert result["user_profile"] == {}
    assert result["memory_events"] == []
    # 对话记忆仍然写入
    conversation = await memory_service.get_memory("s1", memory_type="conversation")
    assert len(conversation) == 1


@pytest.mark.asyncio
async def test_memory_update_skips_short_answer_storage():
    with patch("app.graph.nodes._extract_memory_signals", AsyncMock(return_value=({}, []))):
        state = _update_state("u6", answer="太短")
        await node_memory_update(state)

    conversation = await memory_service.get_memory("s1", memory_type="conversation")
    assert conversation == []


# --- 偏好语义去重 / 矛盾取代 ---

# 单位向量，用于精确控制余弦相似度
_V_HIGH = [0.95, 0.312]   # cos ≈ 0.95（>= _FACT_DEDUP_SIM）
_V_MID = [0.70, 0.714]    # cos ≈ 0.70（落在取代区间）
_V_LOW = [0.0, 1.0]       # cos = 0.0


def test_has_negative_signal_keywords():
    assert _has_negative_signal("我不喜欢 Python") is True
    assert _has_negative_signal("用户讨厌 Java") is True
    assert _has_negative_signal("我改用 Go 了") is True
    assert _has_negative_signal("用户喜欢 Python") is False


def test_classify_no_embedding_falls_back_to_store():
    # 无向量：退化为精确去重，由调用方处理，这里返回 store
    assert _classify_fact_against_existing("用户喜欢 Python", None, []) == ("store", None)


def test_classify_no_active_facts_stores():
    assert _classify_fact_against_existing("用户喜欢 Python", [1.0, 0.0], []) == ("store", None)


def test_classify_semantic_duplicate_skips():
    # 同一偏好换种说法（高相似度、同极性）→ 跳过
    old = {"id": 1, "content": "用户偏好 Python", "embedding": _V_HIGH}
    action, old_id = _classify_fact_against_existing("用户喜欢 Python", [1.0, 0.0], [old])
    assert action == "skip"
    assert old_id is None


def test_classify_polarity_flip_at_high_sim_supersedes():
    # 高相似度但情感相反（用户改口）→ 取代旧记录
    old = {"id": 1, "content": "用户喜欢 Python", "embedding": _V_HIGH}
    action, old_id = _classify_fact_against_existing("用户不喜欢 Python 了", [1.0, 0.0], [old])
    assert action == "supersede"
    assert old_id == 1


def test_classify_polarity_flip_in_band_supersedes():
    # 中等相似度 + 极性相反 + 偏好 → 取代
    old = {"id": 2, "content": "用户喜欢 Python", "embedding": _V_MID}
    action, old_id = _classify_fact_against_existing("我不再用 Python", [1.0, 0.0], [old])
    assert action == "supersede"
    assert old_id == 2


def test_classify_same_polarity_mid_sim_stores():
    # 不同偏好、同极性、中相似度 → 保留（两条都存）
    old = {"id": 3, "content": "用户喜欢 Python", "embedding": _V_MID}
    action, _ = _classify_fact_against_existing("用户喜欢 Java", [1.0, 0.0], [old])
    assert action == "store"


def test_classify_non_pref_not_superseded():
    # 非偏好事实即使极性相反也不做取代（避免误删事实类记忆）
    old = {"id": 4, "content": "用户在北京", "embedding": _V_MID}
    action, _ = _classify_fact_against_existing("用户不在北京", [1.0, 0.0], [old])
    assert action == "store"


def test_classify_low_sim_stores():
    old = {"id": 5, "content": "用户喜欢 Python", "embedding": _V_LOW}
    action, _ = _classify_fact_against_existing("用户喜欢 Python", [1.0, 0.0], [old])
    assert action == "store"


@pytest.mark.asyncio
async def test_memory_update_semantic_dedup_does_not_pile_up():
    """第二轮用不同措辞表达同一偏好时，不应再新增 fact 行（避免堆积）。"""
    v_new = [0.99, 0.141]  # 与已存 fact 余弦≈0.99
    with patch("app.graph.nodes._extract_memory_signals", AsyncMock(return_value=({}, ["偏好用 Python 写代码"]))), \
         patch("app.graph.nodes.memory_service.get_active_fact_events", AsyncMock(return_value=[])), \
         patch("app.graph.nodes.embedding_service.embed_texts", AsyncMock(return_value=[v_new])):
        await node_memory_update(_update_state("u_dedup_a"))  # 首轮：无旧偏好 → 落库 1 条

    stored = await memory_service.get_memory_events("u_dedup_a", limit=100)
    stored_facts = [e for e in stored if e["event_type"] == "fact"]
    assert len(stored_facts) == 1
    old_id = stored_facts[0]["id"]

    # 注入向量，模拟该偏好已被向量化（测试环境默认不联网，embedding 为空）
    from app.services import embedding_service as _emb_svc
    conn = await memory_service._connect()
    try:
        await conn.execute(
            "UPDATE memory_events SET embedding=? WHERE id=?",
            (_emb_svc.encode_vector([1.0, 0.0]), old_id),
        )
        await conn.commit()
    finally:
        await conn.close()

    with patch("app.graph.nodes._extract_memory_signals", AsyncMock(return_value=({}, ["用户喜欢用 Python 编程"]))), \
         patch("app.graph.nodes._generate_profile_summary", AsyncMock(return_value="摘要")), \
         patch("app.graph.nodes.memory_service.get_active_fact_events",
               AsyncMock(return_value=[{"id": old_id, "content": "偏好用 Python 写代码", "embedding": [1.0, 0.0]}])), \
         patch("app.graph.nodes.embedding_service.embed_texts", AsyncMock(return_value=[v_new])):
        await node_memory_update(_update_state("u_dedup_a"))  # 第二轮：语义重复 → 跳过

    facts = [e for e in await memory_service.get_memory_events("u_dedup_a", limit=100) if e["event_type"] == "fact"]
    assert len(facts) == 1  # 未堆积
    assert facts[0]["id"] == old_id


@pytest.mark.asyncio
async def test_memory_update_supersedes_conflicting_preference():
    """用户改口（不再喜欢 X）应取代旧偏好，而非新旧并存。"""
    # 预置旧偏好：用户喜欢 Python
    with patch("app.graph.nodes._extract_memory_signals", AsyncMock(return_value=({}, ["用户喜欢 Python"]))), \
         patch("app.graph.nodes._generate_profile_summary", AsyncMock(return_value="摘要")):
        await node_memory_update(_update_state("u_super"))

    stored = await memory_service.get_memory_events("u_super", limit=100)
    old_facts = [e for e in stored if e["event_type"] == "fact"]
    assert len(old_facts) == 1
    old_id = old_facts[0]["id"]

    from app.services import embedding_service as _emb_svc
    conn = await memory_service._connect()
    try:
        await conn.execute(
            "UPDATE memory_events SET embedding=? WHERE id=?",
            (_emb_svc.encode_vector([1.0, 0.0]), old_id),
        )
        await conn.commit()
    finally:
        await conn.close()

    # 第二轮：用户改口不喜欢 Python
    with patch("app.graph.nodes._extract_memory_signals", AsyncMock(return_value=({}, ["用户不喜欢 Python 了"]))), \
         patch("app.graph.nodes._generate_profile_summary", AsyncMock(return_value="摘要")), \
         patch("app.graph.nodes.memory_service.get_active_fact_events",
               AsyncMock(return_value=[{"id": old_id, "content": "用户喜欢 Python", "embedding": [1.0, 0.0]}])), \
         patch("app.graph.nodes.embedding_service.embed_texts", AsyncMock(return_value=[[0.99, 0.141]])):
        await node_memory_update(_update_state("u_super"))

    events = await memory_service.get_memory_events("u_super", limit=100)
    facts = [e for e in events if e["event_type"] == "fact"]
    active = [e for e in facts if not e["expired_at"]]
    expired = [e for e in facts if e["expired_at"]]
    assert len(active) == 1
    assert active[0]["content"] == "用户不喜欢 Python 了"
    assert len(expired) == 1
    assert expired[0]["id"] == old_id
