"""
Phase 9: Evaluation
30 个测试问题集 + 自动评测脚本
需要先启动 LightRAG Server (9621) 和 Backend (8000)
"""
import asyncio
import json
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import httpx

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

# 测试数据集
TEST_QUESTIONS = [
    # 简单知识问题（10）
    {"id": 1, "query": "What is LangGraph?", "expected_contains": ["LangGraph"], "category": "simple"},
    {"id": 2, "query": "What does StateGraph do in LangGraph?", "expected_contains": ["StateGraph"], "category": "simple"},
    {"id": 3, "query": "What are nodes in LangGraph?", "expected_contains": ["node"], "category": "simple"},
    {"id": 4, "query": "What are edges in LangGraph?", "expected_contains": ["edge"], "category": "simple"},
    {"id": 5, "query": "What is the State in LangGraph?", "expected_contains": ["state"], "category": "simple"},
    {"id": 6, "query": "What framework is LangGraph built on?", "expected_contains": ["LangChain"], "category": "simple"},
    {"id": 7, "query": "What systems inspired LangGraph?", "expected_contains": ["Pregel"], "category": "simple"},
    {"id": 8, "query": "Does LangGraph support async?", "expected_contains": ["async", "synchronous", "asynchronous"], "category": "simple"},
    {"id": 9, "query": "What are the key concepts of LangGraph?", "expected_contains": ["node", "edge", "state"], "category": "simple"},
    {"id": 10, "query": "What is LangGraph used for?", "expected_contains": ["LLM", "application"], "category": "simple"},

    # 跨文档问题（10）
    {"id": 11, "query": "How does LangGraph handle multi-actor applications?", "expected_contains": ["actor", "LangGraph"], "category": "cross_doc"},
    {"id": 12, "query": "What makes LangGraph different from simple LangChain chains?", "expected_contains": ["cyclic", "stateful", "LangGraph"], "category": "cross_doc"},
    {"id": 13, "query": "How does state flow between nodes in LangGraph?", "expected_contains": ["state", "node"], "category": "cross_doc"},
    {"id": 14, "query": "Can LangGraph conditional edges route to different nodes?", "expected_contains": ["conditional", "edge"], "category": "cross_doc"},
    {"id": 15, "query": "What execution modes does LangGraph support?", "expected_contains": ["sync", "async", "execution"], "category": "cross_doc"},
    {"id": 16, "query": "How does LangGraph extend LangChain Expression Language?", "expected_contains": ["LangChain", "cyclic"], "category": "cross_doc"},
    {"id": 17, "query": "What is the relationship between LangGraph nodes and agents?", "expected_contains": ["agent", "node"], "category": "cross_doc"},
    {"id": 18, "query": "How is the computation graph defined in LangGraph?", "expected_contains": ["StateGraph", "node", "edge"], "category": "cross_doc"},
    {"id": 19, "query": "What input does each node receive in LangGraph?", "expected_contains": ["state"], "category": "cross_doc"},
    {"id": 20, "query": "Is LangGraph suitable for production deployments?", "expected_contains": ["production", "deployment"], "category": "cross_doc"},

    # 多跳推理（5）
    {"id": 21, "query": "If I want to build a multi-step agent that remembers previous steps, which LangGraph concept should I use?", "expected_contains": ["state", "StateGraph"], "category": "multi_hop"},
    {"id": 22, "query": "How would you connect two computation steps that depend on each other in LangGraph?", "expected_contains": ["node", "edge"], "category": "multi_hop"},
    {"id": 23, "query": "What combination of LangGraph features enables conditional branching in a workflow?", "expected_contains": ["conditional", "edge"], "category": "multi_hop"},
    {"id": 24, "query": "How does LangGraph's inspiration from Pregel influence its design for multi-actor coordination?", "expected_contains": ["Pregel", "actor", "node"], "category": "multi_hop"},
    {"id": 25, "query": "What would you need to implement a cyclic reasoning loop in LangGraph?", "expected_contains": ["cyclic", "node", "edge"], "category": "multi_hop"},

    # 无法回答（5）
    {"id": 26, "query": "What is the latest version of LangGraph released in 2026?", "expected_contains": [], "category": "unanswerable", "expect_no_hallucination": True},
    {"id": 27, "query": "Who is the CEO of LangChain Inc?", "expected_contains": [], "category": "unanswerable", "expect_no_hallucination": True},
    {"id": 28, "query": "What is LangGraph's pricing plan?", "expected_contains": [], "category": "unanswerable", "expect_no_hallucination": True},
    {"id": 29, "query": "How many lines of code is LangGraph?", "expected_contains": [], "category": "unanswerable", "expect_no_hallucination": True},
    {"id": 30, "query": "What is the phone number for LangGraph support?", "expected_contains": [], "category": "unanswerable", "expect_no_hallucination": True},
]


async def evaluate():
    results = []
    stats = {"total": 0, "retrieval_success": 0, "answer_ok": 0, "router_knowledge": 0, "latencies": []}

    async with httpx.AsyncClient(timeout=120) as client:
        for q in TEST_QUESTIONS:
            print(f"[{q['id']:02d}/{len(TEST_QUESTIONS)}] {q['query'][:60]!r}...", end=" ", flush=True)
            t0 = time.monotonic()
            try:
                resp = await client.post(
                    f"{BACKEND_URL}/chat",
                    json={"query": q["query"], "session_id": f"eval-{q['id']}"},
                )
                data = resp.json()
                latency = time.monotonic() - t0

                answer = data.get("answer", "")
                agent = data.get("agent", "")
                sources = data.get("sources", [])

                retrieval_ok = len(sources) > 0 or q["category"] == "unanswerable"
                answer_ok = all(kw.lower() in answer.lower() for kw in q["expected_contains"]) if q["expected_contains"] else True

                result = {
                    "id": q["id"],
                    "category": q["category"],
                    "query": q["query"],
                    "agent": agent,
                    "answer_length": len(answer),
                    "sources_count": len(sources),
                    "latency": round(latency, 2),
                    "retrieval_ok": retrieval_ok,
                    "answer_ok": answer_ok,
                    "reflection_passed": data.get("reflection_passed", False),
                }
                results.append(result)

                stats["total"] += 1
                if retrieval_ok:
                    stats["retrieval_success"] += 1
                if answer_ok:
                    stats["answer_ok"] += 1
                if agent == "knowledge":
                    stats["router_knowledge"] += 1
                stats["latencies"].append(latency)

                status = "OK" if answer_ok else "FAIL"
                print(f"{status} | agent={agent} | {latency:.1f}s | src={len(sources)}")

            except Exception as e:
                print(f"ERROR: {e}")
                results.append({"id": q["id"], "category": q["category"], "error": str(e)})
                stats["total"] += 1

    # 统计
    n = stats["total"]
    latencies = stats["latencies"]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total questions:       {n}")
    print(f"Retrieval success:     {stats['retrieval_success']}/{n} ({100*stats['retrieval_success']//n}%)")
    print(f"Answer accuracy:       {stats['answer_ok']}/{n} ({100*stats['answer_ok']//n}%)")
    print(f"Router -> knowledge:   {stats['router_knowledge']}/{n}")
    print(f"Avg latency:           {avg_lat:.2f}s")
    print(f"Max latency:           {max(latencies, default=0):.2f}s")
    print(f"Min latency:           {min(latencies, default=0):.2f}s")

    # 按分类统计
    categories = {}
    for r in results:
        cat = r.get("category", "unknown")
        categories.setdefault(cat, {"ok": 0, "total": 0})
        categories[cat]["total"] += 1
        if r.get("answer_ok", False):
            categories[cat]["ok"] += 1

    print("\nBy category:")
    for cat, s in categories.items():
        print(f"  {cat:<20} {s['ok']}/{s['total']}")

    # 保存详细结果
    output_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"summary": stats | {"avg_latency": avg_lat}, "details": results}, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed results saved to: {output_path}")
    return stats


if __name__ == "__main__":
    asyncio.run(evaluate())
