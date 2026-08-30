from langgraph.graph import StateGraph, START, END

from app.graph.state import AgentState
from app.graph.nodes import (
    MAX_REFLECTION,
    node_memory_retrieval,
    node_router,
    node_knowledge_agent,
    node_general_agent,
    node_coding_agent,
    node_vision_agent,
    node_roadmap_agent,
    node_diagnosis_agent,
    node_reflection,
    node_memory_update,
)


def _route_agent(state: AgentState) -> str:
    agent = state.get("agent", "general")
    if agent == "knowledge":
        return "knowledge_agent"
    if agent == "coding":
        return "coding_agent"
    if agent == "vision":
        return "vision_agent"
    if agent == "roadmap":
        return "roadmap_agent"
    if agent == "diagnosis":
        return "diagnosis_agent"
    return "general_agent"


def _route_reflection(state: AgentState) -> str:
    if state.get("reflection_passed", True):
        return "memory_update"
    if state.get("reflection_count", 0) >= MAX_REFLECTION:
        return "memory_update"
    # 未通过且未超限，回退到原始 agent 重试（而非固定 knowledge_agent）
    original = state.get("agent", "general")
    return _route_agent(state)


def build_workflow() -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("memory_retrieval", node_memory_retrieval)
    builder.add_node("router", node_router)
    builder.add_node("knowledge_agent", node_knowledge_agent)
    builder.add_node("general_agent", node_general_agent)
    builder.add_node("coding_agent", node_coding_agent)
    builder.add_node("vision_agent", node_vision_agent)
    builder.add_node("roadmap_agent", node_roadmap_agent)
    builder.add_node("diagnosis_agent", node_diagnosis_agent)
    builder.add_node("reflection", node_reflection)
    builder.add_node("memory_update", node_memory_update)

    builder.add_edge(START, "memory_retrieval")
    builder.add_edge("memory_retrieval", "router")
    builder.add_conditional_edges("router", _route_agent, {
        "knowledge_agent": "knowledge_agent",
        "general_agent": "general_agent",
        "coding_agent": "coding_agent",
        "vision_agent": "vision_agent",
        "roadmap_agent": "roadmap_agent",
        "diagnosis_agent": "diagnosis_agent",
    })
    builder.add_edge("knowledge_agent", "reflection")
    builder.add_edge("general_agent", "reflection")
    builder.add_edge("coding_agent", "reflection")
    builder.add_edge("vision_agent", "reflection")
    builder.add_edge("roadmap_agent", "reflection")
    builder.add_edge("diagnosis_agent", "reflection")
    builder.add_conditional_edges("reflection", _route_reflection, {
        "knowledge_agent": "knowledge_agent",
        "general_agent": "general_agent",
        "coding_agent": "coding_agent",
        "vision_agent": "vision_agent",
        "roadmap_agent": "roadmap_agent",
        "diagnosis_agent": "diagnosis_agent",
        "memory_update": "memory_update",
    })
    builder.add_edge("memory_update", END)

    return builder.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_workflow()
    return _graph
