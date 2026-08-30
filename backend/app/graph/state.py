from typing import Any
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # 用户输入
    query: str
    session_id: str
    user_id: str

    # 路由策略
    agent: str
    model: str
    needs_rag: bool
    needs_memory: bool
    needs_tools: bool

    # 短期对话记忆
    memory_context: dict[str, Any]

    # 长期结构化记忆
    user_profile: dict[str, Any]
    memory_events: list[dict[str, Any]]
    last_turn_context: dict[str, Any]

    # Agent 输出
    answer: str
    sources: list[Any]
    retrieval_mode: str
    latency: float
    used_memories: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]

    # Reflection
    reflection_count: int
    reflection_passed: bool
    reflection_notes: str
