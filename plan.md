你现在是这个项目的主程工程师。

我要开发一个生产倾向的 Agentic RAG 项目。

项目目标：

构建一个面向 AI / Computer Science 学习和代码辅助的多 Agent 知识助手。

核心能力：

1. Multi-Agent
2. Routing
3. LightRAG Knowledge Retrieval
4. Memory
5. Tool Use
6. Reflection
7. Multi-model Routing
8. Streaming
9. Web UI
10. Evaluation / Observability

重要要求：

- 不要一次性生成整个项目。
- 必须按照下面 Phase 0 → Phase 7 顺序执行。
- 每完成一个 Phase 必须运行测试。
- 如果测试失败，先修复，不允许直接进入下一阶段。
- 不要擅自引入没有必要的大型框架。
- 保持模块化设计。
- 所有 API Key 必须通过 .env 管理。
- 禁止把 API Key 写入源码。
- 不要把 LightRAG SDK 深度嵌入主应用。
- LightRAG 使用 Server + REST API 方式集成。
- 主 Agent 项目与 LightRAG 服务解耦。
- 每一步修改后都要说明修改了哪些文件以及原因。
- 不要覆盖已有代码，先检查当前项目结构。
- 如果发现已有实现能够复用，优先复用。

技术方向：

Python
FastAPI
LangGraph
LightRAG
Chroma / LightRAG 自身存储
OpenAI-compatible API
前端使用 React

模型层需要设计成可配置的 Model Provider。

不要把具体模型名称硬编码在业务逻辑中。

==================================================
PHASE 0：项目审计
==================================================

任务：

1. 检查当前项目目录。
2. 分析已有代码。
3. 找出：
   - 已完成的 RAG
   - Router
   - Memory
   - Agent
   - Frontend
   - API
   - 配置文件
4. 不要修改代码。
5. 输出当前项目架构。
6. 给出建议的新目录结构。

建议目标结构：

backend/
├── app/
│   ├── main.py
│   ├── api/
│   ├── agents/
│   │   ├── router.py
│   │   ├── knowledge_agent.py
│   │   ├── coding_agent.py
│   │   └── vision_agent.py
│   ├── services/
│   │   ├── lightrag_client.py
│   │   ├── memory_service.py
│   │   ├── model_service.py
│   │   └── retrieval_service.py
│   ├── models/
│   ├── schemas/
│   ├── config.py
│   └── graph/
│
├── tests/
│
├── .env
├── .env.example
└── requirements.txt

frontend/
├── src/
├── components/
├── pages/
└── services/

lightrag/
├── data/
└── config/

PHASE 0 完成后停止。

==================================================
PHASE 1：LightRAG 独立服务
==================================================

目标：

把 LightRAG 独立运行起来。

不要立即集成主 Agent。

使用官方 LightRAG Server。

优先使用当前官方推荐的安装方式。

需要确认当前版本的：
- 安装方式
- Server 启动方式
- API 配置
- OpenAI-compatible 配置
- WebUI
- Swagger API

参考官方文档：

https://github.com/HKUDS/LightRAG

https://github.com/HKUDS/LightRAG/blob/main/docs/LightRAG-API-Server-zh.md

要求：

1. 创建独立 LightRAG 服务目录。
2. 创建 .env。
3. 配置：
   LLM_BINDING
   LLM_MODEL
   LLM_BINDING_HOST
   LLM_BINDING_API_KEY

4. 配置 Embedding：
   EMBEDDING_BINDING
   EMBEDDING_MODEL
   EMBEDDING_BINDING_HOST
   EMBEDDING_BINDING_API_KEY

5. 使用项目提供的 OpenAI-compatible API。

6. 启动 LightRAG Server。

7. 确认：

GET /health

GET /docs

能够正常访问。

8. 上传一份测试文档。

9. 查询测试文档。

10. 验证 LightRAG 能够正常返回结果。

PHASE 1 验收标准：

- LightRAG Server 正常启动
- WebUI 可以访问
- Swagger 可以访问
- 文档能够插入
- Query 能够返回结果
- API Key 没有出现在 Git 中

完成后停止。

==================================================
PHASE 2：LightRAG 配置优化
==================================================

目标：

根据项目的实际模型供应商优化 LightRAG。

重点：

LightRAG 当前支持 OpenAI-compatible LLM。

不要修改 LightRAG 源码。

需要设计：

基础 LLM：

LLM_MODEL

知识抽取：

EXTRACT / 默认 LLM

查询：

QUERY_LLM_MODEL

关键词：

KEYWORD_LLM_MODEL

如果当前 LightRAG 版本支持 Role-Specific LLM Configuration，
使用角色级模型配置。

模型选择不要写死。

通过 .env 控制。

目标：

文档索引阶段可以使用一个适合知识抽取的模型。

Query 阶段可以使用更强的模型。

Embedding 使用独立模型。

如果当前网关支持：

Qwen3-Embedding-8B
bge-m3
Qwen3-Reranker-8B

优先评估其兼容性。

注意：

Embedding 模型一旦用于已有索引，不要随意更换。

如果必须更换，必须重新建立索引。

完成配置后：

1. 重新索引测试文档
2. 测试 Local / Global / Hybrid 等 LightRAG 查询模式（以当前版本实际支持的 API 为准）
3. 比较结果质量

PHASE 2 完成后停止。

==================================================
PHASE 3：创建 LightRAG REST Client
==================================================

目标：

主 Agent 项目不直接 import LightRAG 内部代码。

创建：

backend/app/services/lightrag_client.py

设计：

class LightRAGClient:

    async def query(...)
    async def insert_document(...)
    async def upload_document(...)
    async def health_check(...)

要求：

1. 使用 httpx。
2. 所有 LightRAG URL 从环境变量读取。
3. 设置 timeout。
4. 处理 HTTP 错误。
5. 处理 LightRAG unavailable。
6. 不允许把 LightRAG API 调用散落在 Agent 代码里。
7. 所有 LightRAG 调用集中在 client 中。

配置：

LIGHTRAG_BASE_URL=
LIGHTRAG_API_KEY=

创建：

backend/app/schemas/lightrag.py

定义：

QueryRequest
QueryResponse
DocumentUploadResponse
HealthResponse

创建单元测试：

tests/test_lightrag_client.py

可以先使用 mock。

验收：

pytest 全部通过。

PHASE 3 完成后停止。

==================================================
PHASE 4：Knowledge Agent
==================================================

目标：

创建真正的 Knowledge Agent。

文件：

backend/app/agents/knowledge_agent.py

职责：

1. 接收用户问题。
2. 判断是否需要知识检索。
3. 调用 LightRAG。
4. 获取上下文。
5. 调用最终 LLM。
6. 返回答案。
7. 保存 retrieval metadata。

结构：

User Query
    ↓
Knowledge Agent
    ↓
LightRAG
    ↓
Context
    ↓
LLM
    ↓
Answer

不要让 Knowledge Agent 直接操作 LightRAG HTTP。

必须：

Knowledge Agent
    ↓
LightRAGClient
    ↓
LightRAG Server

要求：

回答中尽可能保留来源信息。

设计：

KnowledgeAnswer：

answer
sources
retrieval_mode
latency
model

PHASE 4 完成后停止。

==================================================
PHASE 5：Routing
==================================================

目标：

将现在简单的 TaskRouter 升级为真正的 Agent Router。

不要继续使用：

IMAGE_ANALYSIS
CONCEPT_EXPLANATION
TUTORIAL_CREATION
COMPARISON
CODE_GENERATION
CODE_REVIEW
DEBUG_HELP

这种过细的任务分类。

改成能力导向：

KNOWLEDGE
CODING
VISION
GENERAL

Router 输出：

{
    "agent": "knowledge",
    "model": "...",
    "needs_rag": true,
    "needs_memory": true,
    "needs_tools": false
}

设计：

Router
    ↓
┌───────────────┐
│ KNOWLEDGE     │ → KnowledgeAgent
│ CODING        │ → CodingAgent
│ VISION        │ → VisionAgent
│ GENERAL       │ → GeneralAgent
└───────────────┘

模型选择从配置中读取。

不要在 router.py 中写：

if x:
    return "某个具体模型"

而应该使用：

ModelRegistry / ModelConfig。

创建：

backend/app/services/model_registry.py

负责：

- 模型注册
- 模型能力
- 模型名称
- provider
- 是否支持 vision
- 是否支持 tools
- 是否支持 reasoning

例如：

ModelCapability:

chat
reasoning
coding
vision
tool_calling

Router 根据能力需求选择模型。

PHASE 5 完成后停止。

==================================================
PHASE 6：Memory
==================================================

目标：

加入 Agent Memory。

不要让 Memory 和 LightRAG 混在一起。

区分：

LightRAG：

长期知识库

Memory：

用户与 Agent 的交互记忆

设计：

User
 ↓
Memory
 ↓
Router
 ↓
Agent
 ↓
LightRAG
 ↓
Answer
 ↓
Memory Update

Memory 至少支持：

1. Conversation Memory
2. User Preference
3. Important Facts

创建：

backend/app/services/memory_service.py

不要一开始使用复杂数据库。

第一阶段可以使用：

SQLite / PostgreSQL

具体选择根据现有项目决定。

Memory API：

get_memory()
save_memory()
search_memory()
clear_memory()

必须测试：

用户第一次说：

“我正在学习 LangGraph。”

之后再次问：

“给我推荐一个项目。”

Agent 能够读取此前信息。

注意：

Memory 不应该把所有对话原文永久保存。

需要设计：

重要信息提取。

==================================================
PHASE 7：LangGraph Agent Workflow
==================================================

目标：

将整个系统正式变成 Agent Workflow。

使用 LangGraph。

设计：

START
  ↓
Memory Retrieval
  ↓
Router
  ↓
Agent Selection
  ↓
┌─────────────────┐
│ Knowledge Agent │
│ Coding Agent    │
│ Vision Agent    │
│ General Agent   │
└────────┬────────┘
         ↓
      Reflection
         ↓
      Memory Update
         ↓
        END

Reflection 不要无限循环。

最多：

MAX_REFLECTION=2

Reflection 判断：

1. 是否回答了问题
2. 是否有足够证据
3. 是否存在明显幻觉
4. 是否需要再次检索

如果知识不足：

返回 Knowledge Agent。

如果已经满足：

END。

创建：

backend/app/graph/

state.py
nodes.py
workflow.py

定义统一 AgentState。

==================================================
PHASE 8：前端
==================================================

目标：

建立一个真正可展示的 Agentic RAG UI。

前端至少包含：

1. Chat 页面
2. Knowledge Base 页面
3. Agent 状态显示
4. Retrieval 来源
5. Memory 状态
6. 当前模型
7. Tool / Agent Trace

Chat 页面：

用户问题

↓

显示：

Router
→ Knowledge Agent
→ LightRAG
→ Retrieval
→ LLM
→ Reflection

不要直接显示模型内部 chain-of-thought。

只显示安全的 Agent 状态：

“正在分析问题”
“正在检索知识库”
“正在生成回答”
“正在检查答案”

不要展示内部思维过程。

知识库页面：

- 上传文件
- 文件列表
- 索引状态
- 文档数量
- 查询测试

如果 LightRAG WebUI 已经提供知识图谱展示，可以考虑嵌入或跳转到 LightRAG WebUI。

==================================================
PHASE 9：Evaluation
==================================================

创建：

tests/evaluation/

准备至少 30 个测试问题：

10 个简单知识问题
10 个跨文档问题
5 个需要多跳检索的问题
5 个无法回答的问题

测试：

Retrieval

Answer

Hallucination

Router

Memory

统计：

- Retrieval Success Rate
- Answer Accuracy
- Citation / Source Coverage
- Router Accuracy
- Average Latency

记录：

model
retrieval_mode
latency
answer
sources

不要只靠人工“感觉效果不错”。

==================================================
PHASE 10：最终优化
==================================================

检查：

1. API Key 是否泄漏
2. .env 是否进入 .gitignore
3. 是否存在硬编码模型
4. 是否存在硬编码 URL
5. LightRAG 是否可以独立启动
6. 主 Agent 是否可以独立启动
7. LightRAG 挂掉时 Agent 是否能优雅处理
8. Router 是否可以更换模型
9. Embedding 是否可以更换
10. Memory 是否可以清空
11. 所有核心功能是否有测试

最终生成：

README.md

必须包含：

1. 项目介绍
2. 系统架构图
3. 技术栈
4. 环境配置
5. LightRAG 启动
6. Backend 启动
7. Frontend 启动
8. API 文档
9. Agent Workflow
10. Routing 机制
11. Memory 机制
12. RAG 机制
13. Evaluation
14. Demo

最终项目应该能够：

docker compose up

或者按照 README：

LightRAG
Backend
Frontend

分别启动。

最终目标：

这是一个真正可以演示的 Agentic RAG，而不是简单的 Chat with PDF。

==================================================

执行规则
==================================================

现在不要开始写代码。

先执行 PHASE 0。

只做项目审计：

1. 查看目录
2. 查看已有代码
3. 分析已有功能
4. 给出当前架构
5. 给出目标架构
6. 给出 Phase 0 修改计划

不要修改任何文件。

等待我的确认后再执行 PHASE 1。