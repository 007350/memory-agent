import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.health import router as health_router
from app.routes.metrics import router as metrics_router
from app.routes.memory import router as memory_router
from app.routes.roadmap import router as roadmap_router
from app.services.lightrag_client import LightRAGClient
from app.services.model_service import init_registry
from app.graph.workflow import get_graph
from app.tools import init_tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_registry()
    init_tools()
    get_graph()
    LightRAGClient()
    yield

    await LightRAGClient.shutdown()


app = FastAPI(title="Agentic RAG API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(settings, "cors_origins", ["http://localhost:5173"]),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=getattr(settings, "rate_limit_max_requests", 60))

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(memory_router)
app.include_router(metrics_router)
app.include_router(roadmap_router)
