import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

import httpx

os.environ.setdefault("LIGHTRAG_BASE_URL", "http://localhost:9621")
os.environ.setdefault("LIGHTRAG_API_KEY", "")

from app.services.lightrag_client import LightRAGClient, LightRAGUnavailableError
from app.schemas.lightrag import QueryRequest


@pytest.mark.asyncio
async def test_health_check_mock():
    client = LightRAGClient.acquire()
    try:
        fake_response = {
            "status": "healthy",
            "core_version": "1.5.6",
            "api_version": "0328",
            "pipeline_busy": False,
            "configuration": {
                "llm_model": "step-3.7-flash",
                "embedding_model": "Qwen3-Embedding-8B",
            },
        }
        with patch.object(client, "_request", new=AsyncMock(return_value=fake_response)):
            result = await client.health_check()
        assert result.status == "healthy"
        assert result.core_version == "1.5.6"
        assert result.llm_model == "step-3.7-flash"
    finally:
        await client.release()


@pytest.mark.asyncio
async def test_query_mock():
    client = LightRAGClient.acquire()
    try:
        fake_response = {
            "response": "LangGraph is a library for building stateful applications.",
            "references": [{"reference_id": "1", "file_path": "langgraph_overview", "content": None}],
            "response_time": 5.2,
        }
        with patch.object(client, "_request", new=AsyncMock(return_value=fake_response)):
            req = QueryRequest(query="What is LangGraph?", mode="hybrid")
            result = await client.query(req)
        assert "LangGraph" in result.response
        assert len(result.references) == 1
        assert result.references[0].file_path == "langgraph_overview"
    finally:
        await client.release()


@pytest.mark.asyncio
async def test_insert_text_mock():
    client = LightRAGClient.acquire()
    try:
        fake_response = {
            "status": "success",
            "message": "Text received",
            "track_id": "insert_test_123",
        }
        with patch.object(client, "_request", new=AsyncMock(return_value=fake_response)):
            result = await client.insert_text("Test content", file_source="test_doc")
        assert result.status == "success"
        assert result.track_id == "insert_test_123"
    finally:
        await client.release()


@pytest.mark.asyncio
async def test_unavailable_error():
    client = LightRAGClient.acquire()
    try:
        with patch.object(
            client._entry.client,
            "request",
            new=AsyncMock(side_effect=httpx.ConnectError("refused")),
        ):
            with pytest.raises(LightRAGUnavailableError):
                await client.health_check()
    finally:
        await client.release()


@pytest.mark.asyncio
async def test_query_modes_mock():
    """验证 mode 参数被正确透传"""
    client = LightRAGClient.acquire()
    try:
        captured = {}

        async def fake_request(method, path, **kwargs):
            captured.update(kwargs.get("json", {}))
            return {"response": "ok", "references": [], "response_time": 1.0}

        with patch.object(client, "_request", new=fake_request):
            for mode in ("local", "global", "hybrid"):
                req = QueryRequest(query="test", mode=mode)
                await client.query(req)
                assert captured["mode"] == mode
    finally:
        await client.release()


# 鈹€鈹€ 集成测试 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_check_integration():
    client = LightRAGClient.acquire()
    try:
        result = await client.health_check()
        assert result.status == "healthy"
    finally:
        await client.release()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_integration():
    client = LightRAGClient.acquire()
    try:
        req = QueryRequest(query="What are the key concepts in LangGraph?", mode="hybrid")
        result = await client.query(req)
        assert len(result.response) > 50
    finally:
        await client.release()
