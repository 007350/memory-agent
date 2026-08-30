from fastapi import APIRouter, HTTPException, Query

from app.services import memory_service


router = APIRouter()


@router.get("/memory/{session_id}")
async def get_memory(session_id: str, memory_type: str = Query(""), limit: int = Query(20, ge=1, le=200)):
    rows = await memory_service.get_memory(
        session_id,
        memory_type=memory_type or None,
        limit=limit,
    )
    return {"session_id": session_id, "memories": rows}


@router.delete("/memory")
async def clear_memory(session_id: str, memory_type: str = Query("")):
    deleted = await memory_service.clear_memory(
        session_id,
        memory_type=memory_type or None,
    )
    return {"deleted": deleted}


@router.delete("/memory/{session_id}/item/{memory_id}")
async def delete_memory_item(session_id: str, memory_id: int):
    deleted = await memory_service.delete_memory(session_id, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"deleted": deleted}


@router.delete("/memory/{user_id}/events/{event_id}")
async def expire_memory_event(user_id: str, event_id: int):
    expired = await memory_service.expire_memory_event(user_id, event_id)
    if not expired:
        raise HTTPException(status_code=404, detail="event not found")
    return {"expired": expired}


@router.get("/memory/{user_id}/profile")
async def get_memory_profile(user_id: str):
    profile = await memory_service.get_user_profile(user_id)
    return {"user_id": user_id, "profile": profile}


@router.put("/memory/{user_id}/profile")
async def put_memory_profile(user_id: str, payload: dict[str, object]):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="profile must be a JSON object")
    profile = {str(key): str(value) for key, value in payload.items() if str(key)}
    await memory_service.save_structured_memory(user_id=user_id, profile=profile, events=None)
    saved = await memory_service.get_user_profile(user_id)
    return {"user_id": user_id, "profile": saved}


@router.get("/memory/{user_id}/events")
async def get_memory_events(user_id: str, limit: int = Query(20, ge=1, le=200), min_importance: float = Query(0.0)):
    rows = await memory_service.get_memory_events(user_id, limit=limit, min_importance=min_importance)
    return {"user_id": user_id, "events": rows}


@router.delete("/memory/{user_id}/events")
async def clear_memory_events(user_id: str):
    deleted = await memory_service.clear_structured_memory(user_id)
    return {"user_id": user_id, "deleted": deleted}


@router.post("/memory/{user_id}/feedback")
async def memory_feedback(user_id: str, payload: dict[str, object]):
    event_id = payload.get("event_id")
    feedback = str(payload.get("feedback", "")).strip()
    if not isinstance(event_id, int) or feedback not in {"up", "down"}:
        raise HTTPException(status_code=400, detail="event_id and feedback are required")
    saved = await memory_service.save_event_feedback(user_id, event_id, feedback)
    if not saved:
        raise HTTPException(status_code=404, detail="event not found")
    return {"saved": saved}


@router.post("/memory/{session_id}/feedback")
async def session_memory_feedback(session_id: str, payload: dict[str, object]):
    memory_id = payload.get("memory_id")
    feedback = str(payload.get("feedback", "")).strip()
    if not isinstance(memory_id, int) or feedback not in {"up", "down"}:
        raise HTTPException(status_code=400, detail="memory_id and feedback are required")
    saved = await memory_service.save_memory_feedback(session_id, memory_id, feedback)
    if not saved:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"saved": saved}


@router.post("/memory/{user_id}/summary")
async def memory_summary(user_id: str, payload: dict[str, object] | None = None):
    summary = str((payload or {}).get("summary", "")).strip() if isinstance(payload, dict) else ""
    source = str((payload or {}).get("source", "manual") or "manual") if isinstance(payload, dict) else "manual"
    profile = await memory_service.summarize_user_profile(user_id, summary=summary or None, source=source)
    return {"user_id": user_id, "profile": profile}


@router.delete("/memory/{user_id}/rollback")
async def memory_rollback(user_id: str):
    profile = await memory_service.rollback_user_profile(user_id)
    return {"user_id": user_id, "profile": profile}
