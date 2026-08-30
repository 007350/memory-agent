from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi import status

from app.config import settings
from app.exceptions import ChatError, ExternalServiceError
from app.graph.workflow import get_graph
from app.schemas.chat import ChatRequest, ChatResponse


router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION_ERROR", "message": "Query must not be empty"},
        )

    if len(req.query) > getattr(settings, "chat_query_max_length", 4000):
        raise ChatError("Query is too long")

    session_id = req.session_id or str(uuid4())
    try:
        result = await get_graph().ainvoke({
            "query": req.query,
            "session_id": session_id,
            "user_id": req.user_id or session_id,
            "reflection_count": 0,
            "reflection_passed": False,
            "needs_memory": True,
        })
    except ExternalServiceError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})

    return ChatResponse(
        answer=result.get("answer", ""),
        agent=result.get("agent", "general"),
        sources=result.get("sources", []),
        retrieval_mode=result.get("retrieval_mode", "none"),
        reflection_passed=result.get("reflection_passed", False),
        reflection_count=result.get("reflection_count", 0),
        latency=result.get("latency", 0.0),
        session_id=session_id,
        tool_calls=result.get("tool_calls", []),
        used_memories=result.get("used_memories", []),
    )
