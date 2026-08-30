"""
Memory Service -> 基于 SQLite 的异步 Agent 记忆存储。
三种记忆类型：
  - conversation: 对话历史
  - preference:   用户偏好
  - fact:         重要事实

特别注意：不要把用户的所有对话都存下来，只存被 extract() 标记为重要的内容。
"""
import json
import os
import time
from typing import Any

import aiosqlite


_DEFAULT_DB_PATH = os.environ.get("MEMORY_DB_PATH", "memory.db")


async def _ensure_tables(conn: aiosqlite.Connection) -> None:
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            session   TEXT    NOT NULL,
            type      TEXT    NOT NULL,
            content   TEXT    NOT NULL,
            metadata  TEXT    NOT NULL DEFAULT '{}',
            source    TEXT    NOT NULL DEFAULT 'user',
            confidence REAL   NOT NULL DEFAULT 1.0,
            created_at REAL   NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(session);
        CREATE INDEX IF NOT EXISTS idx_memories_type    ON memories(type);
    """)
    await _migrate_memories(conn)
    await conn.commit()


async def _ensure_structured_memory(conn: aiosqlite.Connection) -> None:
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS user_memory_profiles (
            user_id TEXT PRIMARY KEY,
            profile JSON NOT NULL DEFAULT '{}',
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memory_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            content TEXT NOT NULL,
            importance REAL NOT NULL DEFAULT 1.0,
            expired_at REAL,
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL,
            source TEXT NOT NULL DEFAULT 'extraction',
            confidence REAL NOT NULL DEFAULT 1.0,
            relevance REAL NOT NULL DEFAULT 0.0,
            feedback_count INTEGER NOT NULL DEFAULT 0,
            feedback_score REAL NOT NULL DEFAULT 0.0,
            embedding BLOB
        );
        CREATE INDEX IF NOT EXISTS idx_memory_events_user ON memory_events(user_id);
        CREATE INDEX IF NOT EXISTS idx_memory_events_importance ON memory_events(importance);
    """)
    await _migrate_memory_events(conn)
    await conn.commit()


async def _migrate_memory_events(conn: aiosqlite.Connection) -> None:
    columns = {row["name"] for row in await conn.execute_fetchall("PRAGMA table_info(memory_events)")}
    if "embedding" not in columns:
        await conn.execute("ALTER TABLE memory_events ADD COLUMN embedding BLOB")


async def _connect() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(os.environ.get("MEMORY_DB_PATH", _DEFAULT_DB_PATH))
    try:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = aiosqlite.Row
        await _ensure_tables(conn)
        await _ensure_structured_memory(conn)
        await _ensure_roadmap_table(conn)
    except Exception:
        await conn.close()
        raise
    return conn


async def save_memory(
    session: str,
    memory_type: str,
    content: str,
    metadata: dict[str, Any] | None = None,
    source: str = "user",
    confidence: float = 1.0,
) -> int:
    conn = await _connect()
    try:
        cur = await conn.execute(
            "INSERT INTO memories (session, type, content, metadata, source, confidence, created_at) VALUES (?,?,?,?,?,?,?)",
            (session, memory_type, content, json.dumps(metadata or {}), source, float(confidence), time.time()),
        )
        await conn.commit()
        return cur.lastrowid
    finally:
        await conn.close()


async def save_structured_memory(
    user_id: str,
    profile: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> None:
    from app.services import embedding_service

    conn = await _connect()
    try:
        if profile is not None:
            await conn.execute(
                """
                INSERT INTO user_memory_profiles (user_id, profile, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET profile=excluded.profile, updated_at=excluded.updated_at
                """,
                (user_id, json.dumps(profile or {}), time.time()),
            )

        if events:
            # 事件写入前批量向量化；失败则 embedding 为空，检索退化为关键词路径
            contents = [str(item.get("content", "")) for item in events if item.get("content")]
            vectors = await embedding_service.embed_texts(contents) if contents else None
            vector_by_content: dict[str, list[float]] = {}
            if vectors:
                vector_by_content = dict(zip(contents, vectors))

            rows = []
            for item in events:
                content = str(item.get("content", ""))
                if not content:
                    continue
                vector = vector_by_content.get(content)
                rows.append(
                    (
                        user_id,
                        item.get("event_type", "fact"),
                        content,
                        float(item.get("importance", 1.0) or 1.0),
                        item.get("expired_at"),
                        json.dumps(item.get("metadata", {}) or {}),
                        time.time(),
                        item.get("source", "extraction"),
                        float(item.get("confidence", 1.0) or 1.0),
                        float(item.get("relevance", 0.0) or 0.0),
                        int(item.get("feedback_count", 0) or 0),
                        float(item.get("feedback_score", 0.0) or 0.0),
                        embedding_service.encode_vector(vector) if vector else None,
                    )
                )
            if rows:
                await conn.executemany(
                    """
                    INSERT INTO memory_events (user_id, event_type, content, importance, expired_at, metadata, created_at, source, confidence, relevance, feedback_count, feedback_score, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
        await conn.commit()
    finally:
        await conn.close()


async def get_user_profile(user_id: str) -> dict[str, Any]:
    conn = await _connect()
    try:
        async with conn.execute("SELECT profile FROM user_memory_profiles WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(json.loads(row["profile"])) if row and row["profile"] else {}
    finally:
        await conn.close()


async def get_memory_events(
    user_id: str,
    limit: int = 20,
    min_importance: float = 0.0,
) -> list[dict[str, Any]]:
    conn = await _connect()
    try:
        rows = await conn.execute_fetchall(
            """
            SELECT id, event_type, content, importance, expired_at, metadata, created_at,
                   source, confidence, relevance, feedback_count, feedback_score
            FROM memory_events
            WHERE user_id=? AND importance >= ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (user_id, min_importance, limit),
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_memory_events_with_vectors(
    user_id: str,
    limit: int = 100,
    min_importance: float = 0.0,
) -> list[dict[str, Any]]:
    """检索候选集：额外带出 embedding BLOB，由调用方做语义混合打分。"""
    conn = await _connect()
    try:
        rows = await conn.execute_fetchall(
            """
            SELECT id, event_type, content, importance, expired_at, metadata, created_at,
                   source, confidence, relevance, feedback_count, feedback_score, embedding
            FROM memory_events
            WHERE user_id=? AND importance >= ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (user_id, min_importance, limit),
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def find_existing_event_contents(user_id: str, contents: list[str], limit: int = 1000) -> set[str]:
    """返回给定的归一化 content 中已存在于该用户事件流的子集（跨轮去重用）。"""
    wanted = {normalize_event_content(c) for c in contents}
    if not wanted:
        return set()
    conn = await _connect()
    try:
        rows = await conn.execute_fetchall(
            "SELECT content FROM memory_events WHERE user_id=? ORDER BY created_at DESC, id DESC LIMIT ?",
            (user_id, limit),
        )
    finally:
        await conn.close()
    stored = {normalize_event_content(row["content"]) for row in rows}
    return {c for c in wanted if c in stored}


async def get_active_fact_events(user_id: str, limit: int = 500) -> list[dict[str, Any]]:
    """返回该用户未过期的 fact 事件（含 id、content、解码后的 embedding），供语义去重/取代使用。

    embedding 缺失时返回 None，调用方退化为精确去重。
    """
    from app.services import embedding_service

    conn = await _connect()
    try:
        rows = await conn.execute_fetchall(
            "SELECT id, content, embedding FROM memory_events "
            "WHERE user_id=? AND event_type='fact' AND expired_at IS NULL "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
    finally:
        await conn.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        emb = embedding_service.decode_vector(row["embedding"]) if row["embedding"] else None
        out.append({"id": row["id"], "content": row["content"], "embedding": emb})
    return out


async def purge_expired_events(user_id: str | None = None) -> int:
    """物理删除已过期的事件；不带 user_id 时全表清理。"""
    conn = await _connect()
    try:
        if user_id:
            cur = await conn.execute(
                "DELETE FROM memory_events WHERE user_id=? AND expired_at IS NOT NULL AND expired_at <= ?",
                (user_id, time.time()),
            )
        else:
            cur = await conn.execute(
                "DELETE FROM memory_events WHERE expired_at IS NOT NULL AND expired_at <= ?",
                (time.time(),),
            )
        await conn.commit()
        return cur.rowcount
    finally:
        await conn.close()


async def expire_events_of_type(user_id: str, event_type: str) -> int:
    """把该用户某类型的所有未过期事件批量标记过期（用于 summary 事件替换）。"""
    conn = await _connect()
    try:
        cur = await conn.execute(
            "UPDATE memory_events SET expired_at=? WHERE user_id=? AND event_type=? AND expired_at IS NULL",
            (time.time(), user_id, event_type),
        )
        await conn.commit()
        return cur.rowcount
    finally:
        await conn.close()


def normalize_event_content(content: str) -> str:
    """归一化 content 用于跨轮去重：仅压缩空白，保留大小写（中文无影响）。"""
    return " ".join(str(content or "").split()).strip()


async def clear_structured_memory(user_id: str) -> int:
    conn = await _connect()
    try:
        cur = await conn.execute("DELETE FROM memory_events WHERE user_id=?", (user_id,))
        await conn.commit()
        return cur.rowcount
    finally:
        await conn.close()


async def get_memory(
    session: str,
    memory_type: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    conn = await _connect()
    try:
        if memory_type:
            rows = await conn.execute_fetchall(
                "SELECT * FROM memories WHERE session=? AND type=? ORDER BY created_at DESC LIMIT ?",
                (session, memory_type, limit),
            )
        else:
            rows = await conn.execute_fetchall(
                "SELECT * FROM memories WHERE session=? ORDER BY created_at DESC LIMIT ?",
                (session, limit),
            )
        return [_parse_memory_row(r) for r in rows]
    finally:
        await conn.close()


async def search_memory(
    session: str,
    keyword: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    conn = await _connect()
    try:
        rows = await conn.execute_fetchall(
            "SELECT * FROM memories WHERE session=? AND content LIKE ? ORDER BY created_at DESC LIMIT ?",
            (session, f"%{keyword}%", limit),
        )
        return [_parse_memory_row(r) for r in rows]
    finally:
        await conn.close()


async def clear_memory(session: str, memory_type: str | None = None) -> int:
    conn = await _connect()
    try:
        if memory_type:
            cur = await conn.execute(
                "DELETE FROM memories WHERE session=? AND type=?",
                (session, memory_type),
            )
        else:
            cur = await conn.execute("DELETE FROM memories WHERE session=?", (session,))
        await conn.commit()
        return cur.rowcount
    finally:
        await conn.close()


async def search_memory_by_keyword(session: str, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
    conn = await _connect()
    try:
        rows = await conn.execute_fetchall(
            "SELECT * FROM memories WHERE session=? AND content LIKE ? ORDER BY created_at DESC LIMIT ?",
            (session, f"%{keyword}%", limit),
        )
        return [_parse_memory_row(r) for r in rows]
    finally:
        await conn.close()


async def save_memory_feedback(session: str, memory_id: int, feedback: str) -> bool:
    conn = await _connect()
    try:
        async with conn.execute(
            "SELECT metadata FROM memories WHERE session=? AND id=?",
            (session, memory_id),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return False
        metadata = json.loads(row["metadata"])
        feedbacks = metadata.get("feedbacks", [])
        feedbacks.append({"feedback": feedback, "created_at": time.time()})
        metadata["feedbacks"] = feedbacks[-50:]
        await conn.execute(
            "UPDATE memories SET metadata=?, feedback_count=feedback_count+1, feedback_score=feedback_score+? WHERE session=? AND id=?",
            (json.dumps(metadata), 1.0 if feedback == "up" else -1.0, session, memory_id),
        )
        await conn.commit()
        return True
    finally:
        await conn.close()


async def save_event_feedback(user_id: str, event_id: int, feedback: str) -> bool:
    conn = await _connect()
    try:
        async with conn.execute(
            "SELECT id, feedback_count, feedback_score FROM memory_events WHERE user_id=? AND id=?",
            (user_id, event_id),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return False
        count = int(row["feedback_count"] or 0) + 1
        score = float(row["feedback_score"] or 0.0) + (1.0 if feedback == "up" else -1.0)
        await conn.execute(
            "UPDATE memory_events SET feedback_count=?, feedback_score=? WHERE user_id=? AND id=?",
            (count, score, user_id, event_id),
        )
        await conn.commit()
        return True
    finally:
        await conn.close()


async def summarize_user_profile(user_id: str, summary: str | None = None, source: str = "summary") -> dict[str, Any]:
    profile = await get_user_profile(user_id)
    updates: dict[str, Any] = {}
    if summary:
        updates["profile_summary"] = summary
    updates["last_summary_source"] = source
    updates["last_summary_at"] = time.time()
    merged = {**profile, **updates}
    await save_structured_memory(user_id=user_id, profile=merged, events=[
        {
            "event_type": "profile_summary",
            "content": summary or "profile summarized",
            "importance": 1.6,
            "source": source,
            "metadata": {"keys": sorted(profile.keys())},
        }
    ])
    return merged


async def delete_memory(session: str, memory_id: int) -> bool:
    conn = await _connect()
    try:
        cur = await conn.execute(
            "DELETE FROM memories WHERE session=? AND id=?",
            (session, memory_id),
        )
        await conn.commit()
        return cur.rowcount > 0
    finally:
        await conn.close()


async def rollback_user_profile(user_id: str) -> dict[str, Any]:
    profile = await get_user_profile(user_id)
    keys = sorted(profile.keys())
    await save_structured_memory(user_id=user_id, profile={}, events=[
        {
            "event_type": "profile_rollback",
            "content": "rollback profile keys: " + ", ".join(keys),
            "importance": 1.7,
            "source": "admin",
            "metadata": {"keys": keys},
        }
    ])
    return {}


async def expire_memory_event(user_id: str, event_id: int) -> bool:
    conn = await _connect()
    try:
        cur = await conn.execute(
            "UPDATE memory_events SET expired_at=? WHERE user_id=? AND id=? AND expired_at IS NULL",
            (time.time(), user_id, event_id),
        )
        await conn.commit()
        return cur.rowcount > 0
    finally:
        await conn.close()


def _parse_memory_row(row: aiosqlite.Row) -> dict[str, Any]:
    raw = dict(row)
    raw["metadata"] = _safe_json_loads(raw.get("metadata"))
    return raw


def _safe_json_loads(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value is None:
        return {}
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, (dict, list)) else value
        except json.JSONDecodeError:
            return value
    return value


async def _ensure_roadmap_table(conn: aiosqlite.Connection) -> None:
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS learning_roadmaps (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT    NOT NULL,
            doc_ref    TEXT    NOT NULL,
            title      TEXT    NOT NULL,
            steps      TEXT    NOT NULL DEFAULT '[]',
            created_at REAL    NOT NULL,
            updated_at REAL    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_roadmaps_user ON learning_roadmaps(user_id);
    """)
    await conn.commit()


async def save_roadmap(user_id: str, doc_ref: str, title: str, steps: list[dict]) -> int:
    conn = await _connect()
    try:
        now = time.time()
        cur = await conn.execute(
            "INSERT INTO learning_roadmaps (user_id, doc_ref, title, steps, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (user_id, doc_ref, title, json.dumps(steps, ensure_ascii=False), now, now),
        )
        await conn.commit()
        return cur.lastrowid
    finally:
        await conn.close()


async def get_roadmaps(user_id: str) -> list[dict]:
    conn = await _connect()
    try:
        rows = await conn.execute_fetchall(
            "SELECT id, user_id, doc_ref, title, steps, created_at, updated_at FROM learning_roadmaps WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        )
        result = []
        for row in rows:
            d = dict(row)
            d["steps"] = _safe_json_loads(d.get("steps", "[]"))
            result.append(d)
        return result
    finally:
        await conn.close()


async def get_roadmap(roadmap_id: int) -> dict | None:
    conn = await _connect()
    try:
        async with conn.execute(
            "SELECT id, user_id, doc_ref, title, steps, created_at, updated_at FROM learning_roadmaps WHERE id=?",
            (roadmap_id,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["steps"] = _safe_json_loads(d.get("steps", "[]"))
        return d
    finally:
        await conn.close()


async def update_step_done(roadmap_id: int, step_id: int, done: bool) -> bool:
    conn = await _connect()
    try:
        async with conn.execute(
            "SELECT steps FROM learning_roadmaps WHERE id=?", (roadmap_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return False
        steps = _safe_json_loads(row["steps"])
        if not isinstance(steps, list):
            return False
        updated = False
        for step in steps:
            if isinstance(step, dict) and step.get("id") == step_id:
                step["done"] = done
                updated = True
                break
        if not updated:
            return False
        await conn.execute(
            "UPDATE learning_roadmaps SET steps=?, updated_at=? WHERE id=?",
            (json.dumps(steps, ensure_ascii=False), time.time(), roadmap_id),
        )
        await conn.commit()
        return True
    finally:
        await conn.close()


async def delete_roadmap(roadmap_id: int) -> bool:
    conn = await _connect()
    try:
        cur = await conn.execute("DELETE FROM learning_roadmaps WHERE id=?", (roadmap_id,))
        await conn.commit()
        return cur.rowcount > 0
    finally:
        await conn.close()


async def _migrate_memories(conn: aiosqlite.Connection) -> None:
    columns = {row["name"] for row in await conn.execute_fetchall("PRAGMA table_info(memories)")}
    pending = {
        "source": "ALTER TABLE memories ADD COLUMN source TEXT NOT NULL DEFAULT 'user'",
        "confidence": "ALTER TABLE memories ADD COLUMN confidence REAL NOT NULL DEFAULT 1.0",
        "feedback_count": "ALTER TABLE memories ADD COLUMN feedback_count INTEGER NOT NULL DEFAULT 0",
        "feedback_score": "ALTER TABLE memories ADD COLUMN feedback_score REAL NOT NULL DEFAULT 0.0",
    }
    for column, statement in pending.items():
        if column not in columns:
            await conn.execute(statement)

