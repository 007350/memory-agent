from fastapi import APIRouter

from app.middleware.metrics import metrics


router = APIRouter()


@router.get("/metrics")
async def get_metrics():
    return metrics.snapshot()
