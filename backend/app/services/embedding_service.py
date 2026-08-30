"""
Embedding Service -> OpenAI 兼容 /embeddings 接口封装，用于记忆语义检索。

设计约束：
  - 未配置（无 base_url/key/model）时直接返回 None，调用方退化为关键词检索
  - 任何网络/协议异常都吞掉并返回 None，绝不阻塞对话主链路
  - 短文本（query、fact）结果做进程内缓存，避免重复计费与延迟
"""
import hashlib
import logging
import struct
import time
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_CACHE_MAX_ENTRIES = 512
_cache: dict[str, tuple[float, list[float]]] = {}
_CACHE_TTL_SECONDS = 3600.0

_TIMEOUT_SECONDS = 15.0


def is_available() -> bool:
    return bool(settings.embedding_base_url and settings.embedding_api_key and settings.embedding_model)


def _cache_key(text: str) -> str:
    digest = hashlib.sha1(f"{settings.embedding_model}::{text}".encode("utf-8")).hexdigest()
    return digest


def _cache_get(key: str) -> list[float] | None:
    hit = _cache.get(key)
    if not hit:
        return None
    created_at, vector = hit
    if time.time() - created_at > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return vector


def _cache_put(key: str, vector: list[float]) -> None:
    if len(_cache) >= _CACHE_MAX_ENTRIES:
        # 简单过期清扫；仍超限则整体重置（缓存丢了不影响正确性）
        now = time.time()
        for k in [k for k, (t, _) in _cache.items() if now - t > _CACHE_TTL_SECONDS]:
            _cache.pop(k, None)
        if len(_cache) >= _CACHE_MAX_ENTRIES:
            _cache.clear()
    _cache[key] = (time.time(), vector)


async def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """批量向量化。未配置或失败时返回 None（调用方退化为关键词检索）。"""
    if not is_available() or not texts:
        return None

    vectors: list[list[float] | None] = [None] * len(texts)
    pending: dict[int, str] = {}
    for i, text in enumerate(texts):
        normalized = text.strip()
        if not normalized:
            continue
        key = _cache_key(normalized)
        cached = _cache_get(key)
        if cached is not None:
            vectors[i] = cached
        else:
            pending[i] = normalized

    if pending:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                base_url=settings.embedding_base_url,
                api_key=settings.embedding_api_key,
                timeout=_TIMEOUT_SECONDS,
            )
            resp = await client.embeddings.create(
                model=settings.embedding_model,
                input=list(pending.values()),
            )
            data = sorted(resp.data, key=lambda item: item.index)
            for (idx, text), item in zip(pending.items(), data):
                vector = [float(v) for v in item.embedding]
                vectors[idx] = vector
                _cache_put(_cache_key(text), vector)
        except Exception as exc:
            logger.warning("embedding request failed, fallback to keyword scoring: %s", exc)
            return None

    if any(v is None for v in vectors):
        return None
    return [v for v in vectors if v is not None]


async def embed_text(text: str) -> list[float] | None:
    result = await embed_texts([text])
    return result[0] if result else None


def encode_vector(vector: list[float]) -> bytes:
    """float32 小端编码，用于 SQLite BLOB 存储。"""
    return struct.pack(f"<{len(vector)}f", *vector)


def decode_vector(blob: Any) -> list[float] | None:
    """从 BLOB 解码向量；缺省/损坏返回 None。"""
    if not blob:
        return None
    try:
        raw = bytes(blob)
        if not raw or len(raw) % 4 != 0:
            return None
        return [float(v) for v in struct.unpack(f"<{len(raw) // 4}f", raw)]
    except (struct.error, TypeError, ValueError):
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
