import json
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:9621"

DOC_LANGGRAPH = """LangGraph is a library for building stateful, multi-actor applications with LLMs, built on top of LangChain. It extends LangChain Expression Language with the ability to coordinate multiple chains across multiple steps of computation in a cyclic manner.

Key Concepts:
1. StateGraph: The core abstraction in LangGraph. A StateGraph takes a state schema (TypedDict or Pydantic) and lets you define nodes and edges. The state is shared across all nodes.
2. Nodes: Python functions that take the current state and return an update to the state. Each node represents one step in the computation.
3. Edges: Define the transitions between nodes. Can be unconditional (always go from A to B) or conditional (choose next node based on state).
4. Checkpointing: LangGraph supports persistence via checkpointers (e.g., MemorySaver, SqliteSaver). This allows resuming conversations and implementing human-in-the-loop workflows.
5. Multi-Agent Coordination: Multiple agents can share a common state and pass work between each other. A supervisor agent can route tasks to specialized subagents.

Example workflow pattern:
- node_memory_retrieval: loads user profile and recent conversation history
- node_router: classifies query intent, decides which agent handles it
- node_knowledge_agent: retrieves from RAG, generates grounded answer
- node_coding_agent: generates and explains code
- node_reflection: evaluates answer quality; loops back if quality is poor
- node_memory_update: extracts facts and persists to long-term memory

Compiled graph exposes .invoke() and .astream() methods for synchronous and streaming execution. Works with any LangChain-compatible LLM provider.

Advanced LangGraph Features:
- Conditional edges: use add_conditional_edges() with a routing function that inspects state
- Human-in-the-loop: interrupt_before or interrupt_after node names to pause execution
- Subgraphs: nest a compiled graph as a node in a parent graph
- Streaming: stream tokens or full state diffs via .astream_events()
- Persistence: SqliteSaver and PostgresSaver for production checkpointing
- Time travel: replay from any past checkpoint using thread_id + checkpoint_id"""

DOC_LIGHTRAG = """LightRAG is a lightweight, fast RAG server combining knowledge graph storage with vector similarity search.

Architecture:
- KV Storage: stores full documents and text chunks (JsonKVStorage)
- Vector Storage: NanoVectorDB for embedding-based similarity search
- Graph Storage: NetworkX for entity-relation knowledge graph (graphml)
- Document Status Storage: tracks indexing patus per track_id

Retrieval Modes:
- local: searches within related graph context (narrow, precise)
- global: searches across entire knowledge graph (broad, comprehensive)
- hybrid: combines local and global for best coverage (recommended)
- naive: pure vector search without graph traversal
- mix: combines graph and vector results

Insert Pipeline:
1. POST /documents/text with {text, file_source}
2. LightRAG chunks text, extracts entities and relations using LLM (extract role)
3. Builds knowledge graph edges between entities
4. Creates embeddings for chunks (embedding role)
5. Returns track_id; poll /documents/track_status/{track_id} for completion

Query Pipeline:
1. POST /query with {query, mode, top_k}
2. Extract keywords from query (keyword role LLM)
3. Retrieve relevant graph context and vector neighbors
4. Merge and deduplicate context
5. Generate answer using LLM (query role) with retrieved context
6. Return {response, references, response_time}

REST API Endpoints:
- GET /health: server status, LLM model, embedding model, pipeline_busy
- POST /documents/text: insert plain text document
- POST /documents/upload: upload file (multipart/form-data)
- GET /documents/track_status/{track_id}: check indexing status
- POST /query: query knowledge base
- GET /documents: list indexed documents
- DELETE /documents/{doc_id}: delete document from index

LightRAG v1.5.6 uses role-based LLM configuration: extract, keyword, query, vlm roles can use different models and parallelism settings."""

DOC_RAG_SURVEY = """Retrieval-Augmented Generation (RAG) Technology Overview

RAG combines a retrieval component with a generative language model to ground responses in external knowledge.

Naive RAG:
- Simple pipeline: retrieve top-K chunks by vector similarity, prepend to prompt
- Weaknesses: limited context window, no reasoning over retrieved chunks, hallucination on conflicting docs

Advanced RAG:
- Pre-retrieval: query rewriting, HyDE (hypothetical document embedding), step-back prompting
- Retrieval: hybrid search (dense + sparse BM25), re-ranking with cross-encoders, MMR for diversity
- Post-retrieval: context compression, LLM-based filtering, citation tracking

Agentic RAG:
- Agent decides when and how to retrieve (ReAct loop, tool-calling)
- Multi-step retrieval: iterative query refinement based on intermediate results
- Multi-source: query multiple knowledge bases, APIs, databases
- Self-reflection: agent evaluates retrieved context quality and re-queries if insufficient
- LangGraph implementation: router node decides retrieval strategy; reflection node triggers re-retrieval

Graph RAG:
- Builds a knowledge graph from documents (entity extraction + relation extraction)
- Queries traverse graph edges for multi-hop reasoning
- Combines graph traversal with vector similarity (LightRAG hybrid mode)
- Better for: factual QA, relationship queries, domain-specific knowledge

Evaluation Metrics:
- Faithfulness: is the answer grounded in retrieved context?
- Answer Relevance: does the answer address the question?
- Context Precision: how much retrieved context is actually useful?
- Context Recall: was all relevant context retrieved?"""

DOC_PYTHON_ASYNC = """Python Asynchronous Programming with asyncio

Core Concepts:
- Event loop: single-threaded executor that schedules coroutines and I/O callbacks
- Coroutine: function defined with async def; suspended at await points
- Task: scheduled coroutine running concurrently in the event loop
- Future: low-level awaitable representing an eventual result

Key APIs:
- asyncio.run(coro): run a top-level coroutine and block until complete
- asyncio.create_task(coro): schedule coroutine as a Task (runs concurrently)
- asyncio.gather(*coros): run multiple coroutines concurrently, collect results
- asyncio.wait_for(coro, timeout): cancel coroutine if it exceeds timeout
- asyncio.sleep(seconds): yield control back to event loop

aiohttp — Async HTTP client/server:
- aiohttp.ClientSession: connection-pool-aware HTTP client
- async with session.get(url) as resp: non-blocking HTTP request
- await resp.json(): non-blocking response body parsing

FastAPI async patterns:
- async def route handlers run in the event loop, no thread-pool overhead
- Sync handlers auto-run in threadpool via run_in_executor
- Dependency injection supports async def dependencies
- Background tasks: BackgroundTasks.add_task() for fire-and-forget work
- Lifespan events: @asynccontextmanager on app lifespan for startup/shutdown

SQLite async with aiosqlite:
- aiosqlite wraps sqlite3 in a background thread, exposes async interface
- async with aiosqlite.connect(path) as db: obtain connection
- await db.execute(sql, params): parameterized query
- await db.commit(): persist writes

Common pitfalls:
- Never call blocking I/O (requests, open, time.sleep) inside async def — use async alternatives
- asyncio.gather runs coroutines concurrently but still single-threaded; CPU-bound tasks need ProcessPoolExecutor
- Task cancellation: await task.cancel() then handle CancelledError in the coroutine"""

DOC_TRANSFORMER = """Transformer Architecture and Attention Mechanism

Self-Attention:
- Input: sequence of token embeddings X of shape (seq_len, d_model)
- Project to Query Q, Key K, Value V via learned weight matrices
- Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) * V
- Scaled dot-product prevents vanishing gradients for large d_k
- Multi-head attention: run h parallel attention heads, concatenate and project

Positional Encoding:
- Transformers have no inherent sequence order; positional encoding injects position info
- Sinusoidal encoding: PE(pos, 2i) = sin(pos/10000^(2i/d_model))
- Learned absolute positions (BERT) or relative positions (T5, RoPE)
- Rotary Position Embedding (RoPE): used in LLaMA/GPT-NeoX; encodes relative distance in rotation

BERT vs GPT:
- BERT: encoder-only, bidirectional attention, masked language modeling pretraining
  - Good for: classification, NER, sentence similarity, question answering (extractive)
- GPT: decoder-only, causal (unidirectional) attention, next-token prediction
  - Good for: text generation, summarization, chat, code completion
- T5/BART: encoder-decoder, suited for seq2seq tasks (translation, abstractive summarization)

Modern LLM Improvements:
- Flash Attention: IO-aware attention computation, reduces memory from O(n^2) to O(n)
- Grouped Query Attention (GQA): share K/V heads across query heads (fewer KV cache parameters)
- KV Cache: cache past K,V during autoregressive generation to avoid recomputation
- Mixture of Experts (MoE): sparse activation — each token routed to top-k expert FFN layers
- RMSNorm: simpler than LayerNorm, no mean subtraction, used in LLaMA

Training at Scale:
- Data parallelism: replicate model across GPUs, split data batch
- Tensor parallelism: split weight matrices across GPUs (Megatron-LM)
- Pipeline parallelism: split layers across GPUs, micro-batch pipelining
- RLHF: supervised fine-tuning + reward model + PPO for alignment"""

DOCS = [
    ("LangGraph Complete Guide", DOC_LANGGRAPH),
    ("LightRAG Graph Vector RAG System", DOC_LIGHTRAG),
    ("RAG Technology Naive Advanced Agentic", DOC_RAG_SURVEY),
    ("Python Async Programming asyncio FastAPI", DOC_PYTHON_ASYNC),
    ("Transformer Architecture Attention BERT GPT", DOC_TRANSFORMER),
]


def insert_doc(title: str, text: str) -> str:
    payload = json.dumps({"text": text, "file_source": title}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/documents/text",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    return body.get("id") or body.get("track_id") or str(body)


def poll_status(track_id: str, max_wait: int = 120) -> bool:
    url = f"{BASE_URL}/documents/track_status/{track_id}"
    for _ in range(max_wait // 5):
        time.sleep(5)
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                body = json.loads(resp.read())
            status = body.get("status", "")
            print(f"  status: {status}")
            if status in ("completed", "indexed", "done"):
                return True
            if status in ("failed", "error"):
                print(f"  ERROR: {body}")
                return False
        except Exception as e:
            print(f"  poll error: {e}")
    return False


if __name__ == "__main__":
    for title, text in DOCS:
        print(f"Uploading: {title[:50]}")
        try:
            track_id = insert_doc(title, text)
            print(f"  track_id: {track_id}")
            ok = poll_status(track_id)
            print(f"  {'OK' if ok else 'TIMEOUT/FAILED'}")
        except urllib.error.HTTPError as e:
            body = e.read()
            print(f"  HTTP {e.code}: {body[:200]}")
        except Exception as e:
            print(f"  ERROR: {e}")
        print()
