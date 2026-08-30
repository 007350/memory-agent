import os
import httpx
from typing import Any

from app.schemas.lightrag import (
    QueryRequest,
    QueryResponse,
    SourceReference,
    DocumentUploadResponse,
    TrackStatusResponse,
    DocumentStatus,
    HealthResponse,
)

from app.middleware.metrics import InMemoryMetrics
from app.config import settings


class LightRAGUnavailableError(Exception):
    pass


class _ClientEntry:
    def __init__(self, client: httpx.AsyncClient, in_use: bool = False) -> None:
        self.client = client
        self.in_use = in_use


class LightRAGClient:
    _shared_client: httpx.AsyncClient | None = None
    _entries: list[_ClientEntry] = []
    _max_pool = 5

    def __init__(self) -> None:
        self._base_url = settings.lightrag_base_url.rstrip("/")
        self._entry = self._acquire_entry()

    @property
    def metrics(self) -> InMemoryMetrics:
        from app.middleware.metrics import metrics
        return metrics

    @classmethod
    def _shared(cls) -> httpx.AsyncClient:
        if cls._shared_client is None:
            api_key = settings.lightrag_api_key
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if api_key:
                headers["X-API-Key"] = api_key
            cls._shared_client = httpx.AsyncClient(
                base_url=settings.lightrag_base_url.rstrip("/"),
                headers=headers,
                timeout=httpx.Timeout(300.0, connect=10.0),
            )
        return cls._shared_client

    @classmethod
    def _acquire_entry(cls) -> _ClientEntry:
        for entry in cls._entries:
            if not entry.in_use:
                entry.in_use = True
                return entry
        if len(cls._entries) >= cls._max_pool:
            raise RuntimeError("LightRAG client pool exhausted")
        client = cls._shared()
        entry = _ClientEntry(client=client, in_use=True)
        cls._entries.append(entry)
        return entry

    @classmethod
    def acquire(cls) -> "LightRAGClient":
        return cls()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        client = self._entry.client
        try:
            resp = await client.request(method, path, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError as e:
            raise LightRAGUnavailableError(
                f"LightRAG service unavailable at {self._base_url}"
            ) from e
        except httpx.TimeoutException as e:
            raise LightRAGUnavailableError("LightRAG request timed out") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (502, 503, 504):
                raise LightRAGUnavailableError(
                    f"LightRAG service unavailable (HTTP {e.response.status_code})"
                ) from e
            raise RuntimeError(
                f"LightRAG HTTP error {e.response.status_code}: {e.response.text}"
            ) from e

    async def health_check(self) -> HealthResponse:
        data = await self._request("GET", "/health")
        cfg = data.get("configuration", {})
        return HealthResponse(
            status=data.get("status", "unknown"),
            core_version=data.get("core_version"),
            api_version=data.get("api_version"),
            pipeline_busy=data.get("pipeline_busy", False),
            llm_model=cfg.get("llm_model"),
            embedding_model=cfg.get("embedding_model"),
        )

    async def query(self, request: QueryRequest) -> QueryResponse:
        payload = {
            "query": request.query,
            "mode": request.mode,
            "top_k": request.top_k,
            "only_need_context": request.only_need_context,
        }
        data = await self._request("POST", "/query", json=payload)
        refs = [
            SourceReference(
                reference_id=r.get("reference_id", ""),
                file_path=r.get("file_path"),
                content=r.get("content"),
            )
            for r in data.get("references", [])
        ]
        return QueryResponse(
            response=data.get("response", ""),
            references=refs,
            response_time=data.get("response_time"),
        )

    async def insert_text(
        self, text: str, file_source: str | None = None
    ) -> DocumentUploadResponse:
        payload: dict[str, Any] = {"text": text}
        if file_source:
            payload["file_source"] = file_source
        data = await self._request("POST", "/documents/text", json=payload)
        return DocumentUploadResponse(
            status=data.get("status", "unknown"),
            message=data.get("message", ""),
            track_id=data.get("track_id"),
        )

    async def upload_document(self, file_path: str, mime_type: str = "text/plain") -> DocumentUploadResponse:
        """原始上传方法（保留作为fallback）- 会读取整个文件到内存"""
        with open(file_path, "rb") as f:
            content = f.read()
        filename = os.path.basename(file_path)
        try:
            resp = await self._entry.client.post(
                "/documents/upload",
                files={"file": (filename, content, mime_type)},
                timeout=httpx.Timeout(300.0, connect=10.0),
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.ConnectError as e:
            raise LightRAGUnavailableError(
                f"LightRAG service unavailable at {self._base_url}"
            ) from e
        except httpx.TimeoutException as e:
            raise LightRAGUnavailableError("LightRAG upload timed out") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"LightRAG HTTP error {e.response.status_code}: {e.response.text}"
            ) from e
        return DocumentUploadResponse(
            status=data.get("status", "unknown"),
            message=data.get("message", ""),
            track_id=data.get("track_id"),
        )

    async def get_track_status(self, track_id: str) -> TrackStatusResponse:
        data = await self._request("GET", f"/documents/track_status/{track_id}")
        docs = [
            DocumentStatus(
                id=d.get("id", ""),
                status=d.get("status", "unknown"),
                content_summary=d.get("content_summary"),
                chunks_count=d.get("chunks_count"),
                error_msg=d.get("error_msg"),
            )
            for d in data.get("documents", [])
        ]
        return TrackStatusResponse(
            track_id=data.get("track_id", track_id),
            documents=docs,
            status_summary=data.get("status_summary", {}),
        )

    async def release(self) -> None:
        self._entry.in_use = False

    @classmethod
    async def shutdown(cls) -> None:
        for entry in cls._entries:
            entry.in_use = False
        cls._entries.clear()
        if cls._shared_client is not None:
            await cls._shared_client.aclose()
            cls._shared_client = None
