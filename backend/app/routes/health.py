from fastapi import APIRouter

from app.schemas.lightrag import HealthResponse
from app.services.lightrag_client import LightRAGClient, LightRAGUnavailableError
from app.middleware.metrics import metrics


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    try:
        client = LightRAGClient.acquire()
        try:
            h = await client.health_check()
            metrics.record_health(h.status)
            return h
        finally:
            await client.release()
    except LightRAGUnavailableError:
        metrics.record_health("unavailable")
        return HealthResponse(status="degraded", lightrag_status="unavailable")
