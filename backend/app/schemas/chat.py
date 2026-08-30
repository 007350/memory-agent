import time
from dataclasses import dataclass, field
from pydantic import BaseModel

from app.schemas.lightrag import SourceReference


@dataclass
class KnowledgeAnswer:
    answer: str
    sources: list[SourceReference] = field(default_factory=list)
    retrieval_mode: str = "hybrid"
    latency: float = 0.0
    model: str = ""
    tool_calls: list = field(default_factory=list)
    used_memories: list = field(default_factory=list)


class ChatRequest(BaseModel):
    query: str
    session_id: str = ""
    user_id: str = ""


class ToolCall(BaseModel):
    """工具调用信息"""
    name: str
    arguments: dict
    result: str
    error: str = ""
    latency: float = 0.0


class ChatResponse(BaseModel):
    answer: str
    agent: str
    sources: list
    retrieval_mode: str
    reflection_passed: bool
    reflection_count: int
    latency: float
    session_id: str
    tool_calls: list[ToolCall] = []
    used_memories: list = []
