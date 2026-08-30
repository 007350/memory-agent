from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import memory_service

router = APIRouter(prefix="/roadmaps", tags=["roadmaps"])


class StepUpdate(BaseModel):
    done: bool


@router.get("")
async def list_roadmaps(user_id: str = Query(...)):
    roadmaps = await memory_service.get_roadmaps(user_id)
    return {"roadmaps": roadmaps}


@router.get("/{roadmap_id}")
async def get_roadmap(roadmap_id: int):
    roadmap = await memory_service.get_roadmap(roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return roadmap


@router.patch("/{roadmap_id}/steps/{step_id}")
async def update_step(roadmap_id: int, step_id: int, body: StepUpdate):
    ok = await memory_service.update_step_done(roadmap_id, step_id, body.done)
    if not ok:
        raise HTTPException(status_code=404, detail="Roadmap or step not found")
    return {"ok": True}


@router.delete("/{roadmap_id}")
async def delete_roadmap(roadmap_id: int):
    ok = await memory_service.delete_roadmap(roadmap_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"ok": True}
