import os
import pytest
import pytest_asyncio

import sys
sys.path.insert(0, ".")

from app.services import memory_service
from app.services import embedding_service


@pytest.fixture(autouse=True)
def disable_embedding(monkeypatch):
    """关闭 embedding，避免测试触网。"""
    monkeypatch.setattr(embedding_service, "is_available", lambda: False)


@pytest.fixture(autouse=True)
def tmp_db():
    """每个测试使用独立临时数据库文件，避免测试间状态污染。"""
    db_dir = os.path.join(os.path.dirname(__file__), ".tmp")
    os.makedirs(db_dir, exist_ok=True)
    db_file = os.path.join(db_dir, "test_memory.db")
    os.environ["MEMORY_DB_PATH"] = db_file
    yield db_file
    # 清理：删除临时数据库文件
    if os.path.exists(db_file):
        os.remove(db_file)


@pytest.mark.asyncio
async def test_save_and_get():
    row_id = await memory_service.save_memory("s1", "fact", "姝ｅ湪瀛︿範 LangGraph")
    assert isinstance(row_id, int)

    rows = await memory_service.get_memory("s1", memory_type="fact")
    assert len(rows) == 1
    assert rows[0]["content"] == "姝ｅ湪瀛︿範 LangGraph"
    assert rows[0]["type"] == "fact"


@pytest.mark.asyncio
async def test_session_isolation():
    await memory_service.save_memory("session_a", "preference", "鍠滄 Python")
    await memory_service.save_memory("session_b", "preference", "鍠滄 Go")

    a = await memory_service.get_memory("session_a")
    b = await memory_service.get_memory("session_b")

    assert all(r["session"] == "session_a" for r in a)
    assert all(r["session"] == "session_b" for r in b)


@pytest.mark.asyncio
async def test_search():
    await memory_service.save_memory("s2", "fact", "鐢ㄦ埛姝ｅ湪瀛︿範 LangGraph 妗嗘灦")
    await memory_service.save_memory("s2", "fact", "鐢ㄦ埛鍠滄 Python")

    hits = await memory_service.search_memory("s2", "LangGraph")
    assert len(hits) == 1
    assert "LangGraph" in hits[0]["content"]


@pytest.mark.asyncio
async def test_clear_by_type():
    await memory_service.save_memory("s3", "fact", "浜嬪疄1")
    await memory_service.save_memory("s3", "preference", "鍋忓ソ1")

    deleted = await memory_service.clear_memory("s3", memory_type="fact")
    assert deleted == 1

    remaining = await memory_service.get_memory("s3")
    assert len(remaining) == 1
    assert remaining[0]["type"] == "preference"


@pytest.mark.asyncio
async def test_clear_all():
    await memory_service.save_memory("s4", "fact", "浜嬪疄A")
    await memory_service.save_memory("s4", "conversation", "瀵硅瘽A")

    deleted = await memory_service.clear_memory("s4")
    assert deleted == 2

    remaining = await memory_service.get_memory("s4")
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_memory_flow():
    """验证记忆流程：先写入学习内容，再查询能够读取到"""
    session = "flow_test"

    await memory_service.save_memory(session, "fact", "姝ｅ湪瀛︿範 LangGraph")

    memories = await memory_service.get_memory(session, memory_type="fact")
    context = "`n".join(m["content"] for m in memories)

    assert "LangGraph" in context


@pytest.mark.asyncio
async def test_structured_memory_profile_and_events():
    user_id = "user-structured-1"

    await memory_service.save_structured_memory(
        user_id=user_id,
        profile={"name": "Student", "location": "Beijing"},
        events=[
            {"event_type": "fact", "content": "learning LangGraph", "importance": 1.0},
            {"event_type": "fact", "content": "duplicate fact", "importance": 1.0},
            {"event_type": "fact", "content": "duplicate fact", "importance": 0.1},
            {"event_type": "expired", "content": "old goal", "importance": 1.0, "expired_at": 0},
        ],
    )

    profile = await memory_service.get_user_profile(user_id)
    assert profile == {"name": "Student", "location": "Beijing"}

    events = await memory_service.get_memory_events(user_id, limit=20, min_importance=0.0)
    contents = [event["content"] for event in events]
    assert contents == ["old goal", "duplicate fact", "duplicate fact", "learning LangGraph"]

    active_events = [event for event in events if event["event_type"] != "expired"]
    assert all(event["importance"] > 0 for event in active_events)

    deleted = await memory_service.clear_structured_memory(user_id)
    assert deleted >= 1

    after_events = await memory_service.get_memory_events(user_id)
    assert after_events == []


@pytest.mark.asyncio
async def test_save_structured_memory_without_duplicates():
    user_id = "user-structured-2"

    await memory_service.save_structured_memory(
        user_id=user_id,
        profile=None,
        events=[
            {"event_type": "fact", "content": "first", "importance": 1.0},
            {"event_type": "fact", "content": "first", "importance": 1.0},
        ],
    )

    events = await memory_service.get_memory_events(user_id)
    assert len(events) == 2


@pytest.mark.asyncio
async def test_find_existing_event_contents():
    user_id = "dedup-user"
    await memory_service.save_structured_memory(
        user_id=user_id,
        profile=None,
        events=[
            {"event_type": "fact", "content": "喜欢简洁回答", "importance": 1.0},
            {"event_type": "fact", "content": "喜欢 Python", "importance": 1.0},
        ],
    )

    existing = await memory_service.find_existing_event_contents(
        user_id, ["喜欢简洁回答", "偏好中文解释", "喜欢 Python"]
    )
    assert "喜欢简洁回答" in existing
    assert "喜欢 Python" in existing
    assert "偏好中文解释" not in existing


@pytest.mark.asyncio
async def test_normalize_event_content():
    assert memory_service.normalize_event_content("  喜欢  简洁 回答  ") == "喜欢 简洁 回答"
    assert memory_service.normalize_event_content("") == ""


@pytest.mark.asyncio
async def test_purge_expired_events():
    user_id = "purge-user"
    await memory_service.save_structured_memory(
        user_id=user_id,
        profile=None,
        events=[
            {"event_type": "fact", "content": "活跃记忆", "importance": 1.0},
            {"event_type": "fact", "content": "已过期记忆", "importance": 1.0, "expired_at": 0},
        ],
    )
    deleted = await memory_service.purge_expired_events(user_id)
    assert deleted == 1
    remaining = await memory_service.get_memory_events("purge-user", limit=50, min_importance=0.0)
    assert [e["content"] for e in remaining] == ["活跃记忆"]


@pytest.mark.asyncio
async def test_expire_events_of_type():
    user_id = "expire-type-user"
    await memory_service.save_structured_memory(
        user_id=user_id,
        profile=None,
        events=[
            {"event_type": "profile_summary", "content": "第一版", "importance": 1.6},
            {"event_type": "profile_summary", "content": "第二版", "importance": 1.6},
            {"event_type": "fact", "content": "普通偏好", "importance": 1.0},
        ],
    )
    expired = await memory_service.expire_events_of_type(user_id, "profile_summary")
    assert expired == 2
    events = await memory_service.get_memory_events("expire-type-user", limit=50, min_importance=0.0)
    assert all(e["event_type"] != "profile_summary" or e["expired_at"] for e in events)
    assert any(e["event_type"] == "fact" and not e["expired_at"] for e in events)


@pytest.mark.asyncio
async def test_embedding_column_persists():
    """embedding 可用时，事件向量应写入并可从 DB 读回。"""
    from unittest.mock import patch, AsyncMock
    from app.services import embedding_service

    vector = [0.1, 0.2, 0.3]
    async def _fake_embed_texts(texts):
        return [vector for _ in texts]

    with patch.object(embedding_service, "is_available", lambda: True), \
         patch.object(embedding_service, "embed_texts", new=AsyncMock(side_effect=_fake_embed_texts)):
        await memory_service.save_structured_memory(
            user_id="vec-user",
            profile=None,
            events=[{"event_type": "fact", "content": "带向量的事件", "importance": 1.0}],
        )

    rows = await memory_service.get_memory_events_with_vectors("vec-user", limit=50)
    assert len(rows) == 1
    decoded = embedding_service.decode_vector(rows[0]["embedding"])
    assert decoded == pytest.approx([0.1, 0.2, 0.3])
    # 向量不泄露到普通查询
    plain = await memory_service.get_memory_events("vec-user", limit=50)
    assert "embedding" not in plain[0]


@pytest.mark.asyncio
async def test_save_memory_with_source_and_confidence():
    session = "source-session"
    memory_id = await memory_service.save_memory(
        session,
        "preference",
        "喜欢简洁回答",
        source="extraction",
        confidence=0.9,
    )
    assert isinstance(memory_id, int)
    rows = await memory_service.search_memory_by_keyword(session, "简洁")
    assert len(rows) == 1
    assert rows[0]["source"] == "extraction"
    assert rows[0]["confidence"] == 0.9


@pytest.mark.asyncio
async def test_memory_feedback_flow():
    session = "feedback-session"
    memory_id = await memory_service.save_memory(session, "preference", "喜欢代码示例")
    saved = await memory_service.save_memory_feedback(session, memory_id, "up")
    assert saved is True
    rows = await memory_service.search_memory_by_keyword(session, "代码示例")
    assert len(rows) == 1
    metadata = rows[0]["metadata"]
    assert "feedbacks" in metadata
    assert metadata["feedbacks"][-1]["feedback"] == "up"


@pytest.mark.asyncio
async def test_event_feedback_flow():
    user_id = "feedback-event-user"
    await memory_service.save_structured_memory(
        user_id=user_id,
        profile=None,
        events=[{"event_type": "fact", "content": "学习 LangGraph", "source": "extraction"}],
    )
    events = await memory_service.get_memory_events(user_id)
    event_id = events[0]["id"]
    saved = await memory_service.save_event_feedback(user_id, event_id, "up")
    assert saved is True
    events = await memory_service.get_memory_events(user_id)
    assert events[0]["feedback_count"] == 1
    assert events[0]["feedback_score"] == 1.0


@pytest.mark.asyncio
async def test_summarize_and_rollback_profile():
    user_id = "summary-user"
    await memory_service.save_structured_memory(
        user_id=user_id,
        profile={"name": "Student", "location": "Beijing"},
        events=[],
    )
    profile = await memory_service.summarize_user_profile(user_id, summary="学生，在北京学习", source="manual")
    assert profile["profile_summary"] == "学生，在北京学习"
    assert profile["last_summary_source"] == "manual"
    rolled = await memory_service.rollback_user_profile(user_id)
    assert rolled == {}
    events = await memory_service.get_memory_events(user_id)
    assert any(event["event_type"] == "profile_rollback" for event in events)
