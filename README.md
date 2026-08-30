# Agentic RAG

面向 AI / Computer Science 学习和代码辅助的多 Agent 知识助手。

基于 **LangGraph + LightRAG + FastAPI + React** 构建，支持知识图谱检索增强生成（Graph RAG）、多 Agent 智能路由、对话记忆和自我反思循环。除了常规的知识问答 / 编码 / 视觉能力，还内置 **学习路线规划（Roadmap）** 与 **学习诊断（Diagnosis）** 两个 Agent，帮助学习者围绕知识点生成可追踪的学习路径并评估掌握情况。

---

## 目录

- [功能特性](#功能特性)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [环境要求](#环境要求)
- [快速启动](#快速启动)
- [环境变量配置](#环境变量配置)
- [上传知识库文档](#上传知识库文档)
- [API 文档](#api-文档)
- [Agent 工作流详解](#agent-工作流详解)
- [学习路线与学习诊断](#学习路线与学习诊断)
- [记忆系统](#记忆系统)
- [模型配置](#模型配置)
- [运行测试](#运行测试)
- [评测结果](#评测结果)
- [常见问题](#常见问题)

---

## 功能特性

- **多 Agent 路由**：根据问题类型自动分配到 Knowledge / Coding / Vision / Roadmap / Diagnosis / General 六个 Agent
- **Graph RAG**：使用 LightRAG 构建知识图谱，支持 Local / Global / Hybrid 三种检索模式
- **学习路线规划（Roadmap）**：从用户问题中提取主题，结合知识库检索生成 5~10 步结构化学习路线，可勾选进度、删除、重规划
- **学习诊断（Diagnosis）**：结合学习路线进度、用户画像与近期记忆，生成含总体进度 / 强项 / 薄弱点 / 下一步建议的诊断报告
- **对话记忆**：SQLite 持久化存储会话记忆、用户画像、长期事件；偏好事实自动语义去重，避免重复堆积
- **自我反思**：答案质量检查，不满足条件时自动重试（最多 2 次），失败后回到**原 Agent** 而非强制知识问答
- **服务降级**：LightRAG 不可用时自动降级为纯 LLM 回答
- **Tool Use**：支持 Python 代码执行（python_repl）和网络搜索（Firecrawl）工具
- **前端 UI**：对话界面 + 知识库管理 + 学习路线 + 记忆面板 + Agent 状态展示 + 工具调用可视化

---

## 系统架构

```
用户浏览器 (React :5173)
        |
        v
FastAPI Backend :8000
        |
    LangGraph Workflow
    +------------------------------------------------------------+
    |  memory_retrieval                          |             |
    |       |                                    |             |
    |     router  (step-3.5-flash)               |             |
    |       |                                    |             |
    |  +----------+----------+---------+---------+---------+    |
    |  knowledge  coding   vision  roadmap  diagnosis  general  |
    |  agent      agent    agent   agent    agent     agent    |
    |       |                                    |             |
    |   reflection (质量检查, max 2 retries)      |             |
    |       |                                    |             |
    |   memory_update                            |             |
    +------------------------------------------------------------+
        |
    LightRAG Server :9621
        |
    OpenAI-compatible LLM + Embedding API
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 19 + TypeScript + Vite |
| 后端 | FastAPI + LangGraph 1.2.6 |
| RAG | LightRAG 1.5.6 (Graph-based RAG) |
| LLM | 任意 OpenAI-compatible API（默认 StepFun） |
| Embedding | 任意 OpenAI-compatible Embedding API（记忆语义检索 + LightRAG 索引） |
| 记忆 | SQLite via aiosqlite |
| 测试 | pytest + pytest-asyncio |

---

## 目录结构

```
hackthon/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI 入口
│   │   ├── config.py                  # 环境变量配置（只读 env，不硬编码密钥）
│   │   ├── agents/
│   │   │   ├── router.py              # Agent 路由器（含时间敏感/路线/诊断关键词兜底）
│   │   │   ├── knowledge_agent.py     # 知识检索 Agent
│   │   │   ├── coding_agent.py        # 代码辅助 Agent
│   │   │   ├── vision_agent.py        # 视觉 Agent
│   │   │   ├── roadmap_agent.py        # 学习路线规划 Agent
│   │   │   ├── diagnosis_agent.py      # 学习诊断 Agent
│   │   │   └── general_agent.py        # 通用 Agent
│   │   ├── graph/
│   │   │   ├── state.py               # LangGraph AgentState
│   │   │   ├── nodes.py               # 各节点实现（含事实语义去重/取代）
│   │   │   └── workflow.py            # LangGraph 工作流定义
│   │   ├── services/
│   │   │   ├── lightrag_client.py     # LightRAG REST 客户端
│   │   │   ├── memory_service.py       # 记忆服务（SQLite）
│   │   │   ├── model_service.py        # 模型注册初始化
│   │   │   ├── model_registry.py       # 模型注册表
│   │   │   └── embedding_service.py     # Embedding 封装（语义检索用）
│   │   ├── tools/
│   │   │   ├── python_repl.py         # Python 代码执行工具
│   │   │   ├── web_search.py          # 网络搜索工具（Firecrawl）
│   │   │   ├── base.py                # 工具基类
│   │   │   └── exceptions.py          # 工具异常
│   │   ├── routes/
│   │   │   ├── chat.py                # /chat
│   │   │   ├── documents.py           # /documents
│   │   │   ├── memory.py              # /memory（画像/事件/反馈）
│   │   │   ├── roadmap.py             # /roadmaps（学习路线）
│   │   │   ├── health.py              # /health
│   │   │   └── metrics.py             # /metrics
│   │   └── schemas/                   # Pydantic 数据模型
│   ├── tests/
│   │   ├── test_lightrag_client.py
│   │   ├── test_memory_service.py
│   │   ├── test_router.py
│   │   ├── test_nodes.py
│   │   ├── test_tools.py
│   │   └── evaluation/
│   │       └── eval_rag.py            # 30 题端到端评测
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── ChatPage.tsx           # 对话主界面
│   │   │   ├── KnowledgePage.tsx      # 知识库管理
│   │   │   └── RoadmapPage.tsx        # 学习路线（勾选进度/删除/展开）
│   │   ├── components/
│   │   │   ├── RoadmapStats.tsx       # 路线完成率统计（环形图 + 条形图）
│   │   │   └── ToolCallDisplay.tsx    # 工具调用可视化
│   │   ├── services/
│   │   │   └── api.ts                 # API 客户端
│   │   └── hooks/                     # 自定义 hooks
│   └── package.json
├── lightrag/
│   ├── .env.example
│   └── data/                          # 向量索引（不进 Git）
├── start.bat                          # Windows 一键启动脚本
├── docker-compose.yml
└── .gitignore
```

---

## 环境要求

- Python 3.11+
- Node.js 18+
- 可访问的 OpenAI-compatible **LLM API**（StepFun / OpenAI / 其他兼容接口）
- 可访问的 OpenAI-compatible **Embedding API**（记忆语义检索 + LightRAG 建索引）
- 可选：Firecrawl API（网络搜索工具）

> 密钥只放在本地 `.env` 文件中（已被 `.gitignore` 忽略），**不要**提交到仓库。复制 `.env.example` 后填入真实值即可。

---

## 快速启动

### 方式一：Windows 一键启动（推荐）

1. 完成[环境变量配置](#环境变量配置)
2. 安装依赖：

```bash
pip install "lightrag-hku[api]==1.5.6"
pip install -r backend/requirements.txt
cd frontend && npm install
```

3. 双击 `start.bat`，自动打开三个服务窗口

4. 等待约 10 秒，访问 http://localhost:5173

---

### 方式二：手动逐步启动

**第一步：启动 LightRAG Server（端口 9621）**

```bash
pip install "lightrag-hku[api]==1.5.6"
cd lightrag

# Windows
set PYTHONUTF8=1 && lightrag-server

# Linux / macOS
PYTHONUTF8=1 lightrag-server
```

验证：`curl http://localhost:9621/health` 返回 `{"status":"healthy",...}`

**第二步：启动 Backend（端口 8000）**

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

验证：`curl http://localhost:8000/health`

**第三步：启动 Frontend（端口 5173）**

```bash
cd frontend
npm install
npm run dev
```

访问：http://localhost:5173

---

### 方式三：Docker Compose

```bash
# 先完成环境变量配置
cp lightrag/.env.example lightrag/.env
cp backend/.env.example backend/.env
# 编辑两个 .env 文件填入 API Key（docker-compose 通过 env_file 引用，不会写死在 yml）

docker compose up
```

---

## 环境变量配置

> 所有密钥均为占位符示例。**真实值只写在 `.env` 中，该文件已被 `.gitignore` 忽略。**

### LightRAG 配置（`lightrag/.env`）

```bash
cp lightrag/.env.example lightrag/.env
```

编辑 `lightrag/.env`：

```env
# LLM（用于知识抽取和查询生成）
LLM_BINDING=openai
LLM_MODEL=step-3.7-flash
LLM_BINDING_HOST=https://api.stepfun.com/step_plan/v1
LLM_BINDING_API_KEY=your_llm_api_key_here

# Embedding（用于向量检索，建立索引后不可更换）
EMBEDDING_BINDING=openai
EMBEDDING_MODEL=Qwen3-Embedding-8B
EMBEDDING_BINDING_HOST=http://your-embedding-host/v1
EMBEDDING_BINDING_API_KEY=your_embedding_api_key_here

# 维度必须与 Embedding 模型匹配
EMBEDDING_DIM=4096   # Qwen3-Embedding-8B=4096 / text-embedding-ada-002=1536

HOST=0.0.0.0
PORT=9621
WORKING_DIR=./data
```

LightRAG 还支持按角色使用不同模型（降低成本）：

```env
EXTRACT_LLM_MODEL=step-3.5-flash    # 知识抽取用轻量模型
KEYWORD_LLM_MODEL=step-3.5-flash    # 关键词提取用轻量模型
QUERY_LLM_MODEL=step-3.7-flash      # 查询生成用主力模型
```

### Backend 配置（`backend/.env`）

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`：

```env
# LLM API
LLM_BASE_URL=https://api.stepfun.com/step_plan/v1
LLM_API_KEY=your-llm-api-key-here
LLM_MODEL_MAIN=step-3.7-flash       # 主力模型（回答生成）
LLM_MODEL_LIGHT=step-3.5-flash      # 轻量模型（路由判断）

# LightRAG Server 地址
LIGHTRAG_BASE_URL=http://localhost:9621
LIGHTRAG_API_KEY=                   # 如果 LightRAG 未启用鉴权则留空

# 记忆数据库路径（SQLite，已被 .gitignore 忽略）
MEMORY_DB_PATH=memory.db

# Embedding（OpenAI-compatible，用于记忆语义检索；留空则退化为关键词检索）
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=your-embedding-api-key-here
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
EMBEDDING_DIM=4096

# 记忆调优
MEMORY_SEMANTIC_TOP_K=20            # 检索返回的事件上限
MEMORY_DECAY_HALF_LIFE_DAYS=14      # 记忆时间衰减半衰期（天）
MEMORY_CONTEXT_BUDGET_CHARS=3000    # 注入上下文的字符预算
MEMORY_EVENT_SNIPPET_CHARS=200      # 单条事件摘要长度

# 网络搜索（Firecrawl，可选）
FIRECRAWL_API_KEY=your-firecrawl-api-key-here

# 工具配置
PYTHON_REPL_TIMEOUT=5               # python_repl 执行超时（秒）
PYTHON_REPL_MAX_OUTPUT=2000         # 输出截断长度
```

> **注意**：多个 `LLM_API_KEY` 可以是同一个 Key，只要 API 支持即可。

---

## 上传知识库文档

启动三个服务后，有两种方式上传文档：

### 方式一：前端界面

1. 打开 http://localhost:5173
2. 切换到「知识库」标签页
3. 在「上传文档」区域粘贴文档内容
4. 填写来源标识（可选，如 `langchain_tutorial`）
5. 点击「上传并建立索引」
6. 等待 LightRAG 处理（可在 http://localhost:9621 查看进度）

### 方式二：批量上传脚本

项目根目录提供 `upload_docs.py` 脚本，内置 5 篇 AI/CS 领域文档：

```bash
python upload_docs.py
```

### 方式三：直接调用 API

```bash
curl -X POST http://localhost:9621/documents/text \
  -H "Content-Type: application/json" \
  -d '{"text": "文档内容...", "file_source": "文档标题"}'
```

---

## API 文档

FastAPI 自动生成交互式文档：http://localhost:8000/docs

### 对话与文档

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /health | 服务健康检查（含 LightRAG 状态）|
| POST | /chat | 发送对话，返回 Agent 答案 |
| POST | /documents | 上传文本到 LightRAG 知识库 |
| POST | /documents/upload | 上传文档建立索引 |
| GET | /documents/{track_id}/status | 查询文档处理状态 |
| GET | /metrics | 服务指标（请求数、延迟等）|

### 学习路线（Roadmap）

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /roadmaps | 列出该用户的学习路线 |
| GET | /roadmaps/{roadmap_id} | 获取单条路线详情 |
| PATCH | /roadmaps/{roadmap_id}/steps/{step_id} | 更新某一步的完成状态 |
| DELETE | /roadmaps/{roadmap_id} | 删除路线 |

### 记忆与画像（Memory）

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /memory/{session_id} | 获取会话记忆列表 |
| DELETE | /memory | 清除全部会话记忆 |
| DELETE | /memory/{session_id}/item/{memory_id} | 删除单条会话记忆 |
| GET | /memory/{user_id}/profile | 获取用户长期画像 |
| PUT | /memory/{user_id}/profile | 编辑长期画像字段 |
| POST | /memory/{user_id}/summary | 生成 / 刷新画像摘要 |
| DELETE | /memory/{user_id}/rollback | 回滚（清空）画像字段 |
| GET | /memory/{user_id}/events | 获取记忆事件流 |
| DELETE | /memory/{user_id}/events | 清空记忆事件 |
| DELETE | /memory/{user_id}/events/{event_id} | 删除单条记忆事件 |
| POST | /memory/{user_id}/feedback | 给记忆事件反馈（有用 / 没用）|
| POST | /memory/{session_id}/feedback | 给会话记忆反馈 |

### POST /chat 示例

请求：

```json
{
  "query": "What is LangGraph?",
  "session_id": "session-abc123",
  "user_id": "user-xyz"
}
```

响应：

```json
{
  "answer": "LangGraph is a framework built on LangChain for building stateful, multi-actor applications...",
  "agent": "knowledge",
  "sources": [
    {"id": "chunk-001", "file_path": "langgraph_overview", "content": "..."}
  ],
  "retrieval_mode": "hybrid",
  "reflection_passed": true,
  "reflection_count": 0,
  "latency": 5.3,
  "session_id": "session-abc123"
}
```

---

## Agent 工作流详解

每条消息经过以下节点处理：

```
query 到达
  |
  v
memory_retrieval    从 SQLite 加载该用户的历史对话记忆
  |
  v
router              用轻量模型判断 agent 类型和是否需要 RAG
  |                  （时间敏感/学习路线/学习诊断类问题有关键词兜底，避免误判）
  +---> knowledge_agent   调用 LightRAG hybrid 检索 + LLM 生成
  |                       LightRAG 不可用时自动降级为纯 LLM
  +---> coding_agent      代码编写/调试专项
  +---> vision_agent      图片/视觉内容（需多模态模型）
  +---> roadmap_agent     学习路线规划（抽取主题 → 知识库检索 → 生成步骤）
  +---> diagnosis_agent   学习诊断（路线进度 + 画像 + 事件 → 诊断报告）
  +---> general_agent     闲聊/通用问题，直接 LLM 回答
  |
  v
reflection          答案质量检查
                    失败条件：回答长度 < 20 字 或 含 "No relevant context"
                    检查通过 -> memory_update
                    检查失败 -> 重回原 Agent 重试（最多 2 次）
  |
  v
memory_update       将本轮对话关键信息写入记忆（偏好自动语义去重）
  |
  v
返回 ChatResponse
```

### 路由规则

| 问题类型 | 路由到 |
|---------|--------|
| 知识问答、概念解释、文档检索 | knowledge |
| 代码编写、调试、代码审查 | coding |
| 图片分析、多模态任务 | vision |
| 学习路线规划（"帮我规划…的学习路线"等）| roadmap |
| 学习诊断（"我学得怎么样"等）| diagnosis |
| 闲聊、简单问题、其他 | general |
| 天气 / 新闻 / 股价等实时问题 | general + 网络搜索工具 |

---

## 学习路线与学习诊断

### 学习路线（Roadmap）

当用户表达学习意图（如「帮我规划 LangGraph 的学习路线」）时，请求被路由到 `roadmap_agent`：

1. 轻量模型从用户话中抽主题（`doc_name`）；
2. 拿主题去 LightRAG 做 **hybrid 检索**；服务不可用或返回「无相关内容」时降级为占位上下文，不中断；
3. 上下文截断 3000 字后交给主力模型，要求返回 5~10 步的 JSON 数组（逐条校验，缺失标题的丢弃，步骤 id 强制重排序）；
4. 落库 `learning_roadmaps` 表，并拼成 Markdown 回给用户。

前端「学习路线」页支持查看 / 勾选完成 / 删除 / 展开，统计面板（`RoadmapStats`）用纯手写 SVG 环形图 + 条形图展示完成率。

### 学习诊断（Diagnosis）

`diagnosis_agent` 把**学习路线进度 + 用户画像 + 近 50 条记忆事件**一起喂给模型，生成含「总体进度 / 强项 / 薄弱点 / 下一步建议」的 Markdown 诊断报告，帮助用户评估掌握情况并决定下一步学什么。

---

## 记忆系统

记忆分三层，互不干扰：

| 类型 | 说明 | 存储 |
|------|------|------|
| 对话记忆 | 本次会话的关键信息（事实、偏好）| SQLite，按 session_id 隔离 |
| 用户画像 | 跨会话的长期用户特征 | SQLite，按 user_id 存储 |
| 记忆事件 | 每次记忆更新的事件日志 | SQLite，支持反馈和过期标记 |

**偏好自动去重**：每轮抽取的偏好事实会做跨轮精确去重；当 Embedding 可用时，还会做**语义去重**——同一偏好换种说法（"喜欢用 Python" / "偏好 Python"）不会重复堆积；若用户改口（"我不再喜欢 Python"），旧记录会被标记为过期并由新记录取代。无向量时自动退化为精确去重。

前端「查看记忆」面板支持：

- 查看/删除对话记忆条目
- 查看/编辑用户画像、生成画像摘要、回滚画像
- 查看记忆事件历史，标记「有用 / 没用」

---

## 模型配置

模型通过 `ModelRegistry` 统一管理，不在业务代码中硬编码（路由也不会信任 LLM 自填的模型名，统一从注册表取默认值）。

更换模型只需修改 `backend/.env`：

```env
LLM_MODEL_MAIN=gpt-4o          # 换成任意支持 OpenAI 格式的模型
LLM_MODEL_LIGHT=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
```

**Embedding 模型注意事项**：

- 一旦用某个 Embedding 模型建立了索引，**不可更换**
- 更换必须清空 `lightrag/data/` 目录并重新上传所有文档
- 更换后需同步修改 `lightrag/.env` 中的 `EMBEDDING_DIM`
- 后端记忆语义检索用的 Embedding 与 LightRAG 索引可以不同模型，独立配置（`backend/.env` 的 `EMBEDDING_*`）

---

## 运行测试

```bash
cd backend

# 单元测试（无需服务运行，约 6 秒）
pytest tests/ --ignore=tests/evaluation -v

# 集成测试（需要 LightRAG 在 9621 运行）
pytest tests/ -m integration -v

# 端到端评测（需要 LightRAG + Backend 都运行）
python tests/evaluation/eval_rag.py
```

测试覆盖范围：

- `test_lightrag_client.py` — LightRAG 客户端 mock 测试
- `test_memory_service.py` — 记忆服务增删改查
- `test_router.py` — Agent 路由器逻辑（含路线/诊断关键词兜底）
- `test_nodes.py` — LangGraph 节点单元测试（含事实语义去重/取代）
- `test_tools.py` — 工具（python_repl / web_search）测试
- `test_knowledge_agent.py` — Knowledge Agent mock 测试

---

## 评测结果

30 题端到端自动评测，知识库 7 篇文档（LangGraph、LightRAG、RAG Survey、Python Async、Transformer 等）。

| 类别 | 准确率 |
|------|--------|
| simple（简单知识问答）| 10/10 |
| cross_doc（跨文档问答）| 10/10 |
| multi_hop（多跳推理）| 5/5 |
| unanswerable（无法回答的问题）| 5/5 |
| **总计** | **30/30 (100%)** |

检索成功率 96%（29/30），平均延迟 27.4s。

---

## 常见问题

**Q: 启动时提示 `lightrag-server not found`**

`start.bat` 使用完整路径调用，如果你的 Python 虚拟环境不在 `D:\Dev\envs\lang\`，需要修改 `start.bat` 第 8 行的路径：

```bat
set LIGHTRAG=你的虚拟环境路径\Scripts\lightrag-server.exe
```

---

**Q: 上传文档后查询没有检索到内容**

1. 确认文档状态为 `processed`：访问 http://localhost:9621 查看文档列表
2. LightRAG 建立图谱需要时间，大文档可能需要 1-5 分钟
3. 可以查看 LightRAG 窗口的日志确认是否有报错

---

**Q: 回答很慢（超过 30 秒）**

正常现象。LightRAG hybrid 检索需要多次 LLM 调用（关键词抽取 + 图谱查询 + 答案生成），加上 Reflection 节点，首次响应 10-30s 是正常范围。LLM 开启缓存后重复问题会快很多。

---

**Q: 规划学习路线总是失败 / 被当成知识问答**

历史版本中「帮我规划学习路线」会被路由到 knowledge Agent，且反思重试会强制踢回 knowledge。当前版本已在路由层加入**学习路线关键词兜底**，反思失败也会回到**原 Agent**，该问题已修复。若仍异常，确认 `router.py` 的 `_ROADMAP_KEYWORDS` 是否覆盖你的说法。

---

**Q: 调用 Python / 搜索工具报 "Execution failed"**

历史版本 `python_repl` 生成子进程脚本存在引号转义 bug。当前版本已改为字符串拼接并暴露子进程 stderr / 返回码，报错信息会带异常类型与 stderr 内容，便于定位。

---

**Q: 更换其他 LLM API（如 OpenAI）**

只需修改 `backend/.env` 和 `lightrag/.env` 中的 `HOST`、`API_KEY`、`MODEL` 三个字段，无需改代码。

---

**Q: 前端显示「后端服务异常」**

按顺序检查：
1. `curl http://localhost:8000/health` — 确认 Backend 在运行
2. `curl http://localhost:9621/health` — 确认 LightRAG 在运行
3. 查看 Backend 窗口日志，找具体报错原因

---

**Q: 不小心要把 `.env` 提交到 Git 了**

`.env` 已在 `.gitignore` 中忽略，正常 `git add` 不会纳入。若曾用 `git add -f` 强制加入，可用 `git rm --cached backend/.env lightrag/.env` 撤销跟踪，再提交。
