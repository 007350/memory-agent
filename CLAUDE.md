# Agentic RAG — 项目工程规范

## 项目简介

面向 AI / Computer Science 学习和代码辅助的多 Agent 知识助手。
基于 LangGraph + LightRAG + FastAPI + React 构建。

## 环境信息

| 项目 | 值 |
|------|----|
| Python | 3.11.15 (D:/Dev/envs/lang/python.exe) |
| Node | v24.16.0 |
| LLM API | https://api.stepfun.com/step_plan/v1 |
| LLM 模型 | step-3.7-flash (主力), step-3.5-flash (轻量) |
| Embedding | 本地 HuggingFace 缓存 (C盘) |

## 目录结构

```
hackthon/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── agents/
│   │   │   ├── router.py
│   │   │   ├── knowledge_agent.py
│   │   │   ├── coding_agent.py
│   │   │   ├── vision_agent.py
│   │   │   └── general_agent.py
│   │   ├── services/
│   │   │   ├── lightrag_client.py
│   │   │   ├── memory_service.py
│   │   │   ├── model_service.py
│   │   │   ├── model_registry.py
│   │   │   └── retrieval_service.py
│   │   ├── models/
│   │   ├── schemas/
│   │   │   ├── lightrag.py
│   │   │   ├── chat.py
│   │   │   └── memory.py
│   │   ├── graph/
│   │   │   ├── state.py
│   │   │   ├── nodes.py
│   │   │   └── workflow.py
│   │   └── config.py
│   ├── tests/
│   │   └── evaluation/
│   ├── .env
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   └── package.json
├── lightrag/
│   ├── data/
│   └── .env
├── .gitignore
├── docker-compose.yml
└── README.md
```

## 执行规范

### Phase 顺序
Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10
每个 Phase 完成并通过测试后才能进入下一个。

### 核心约束
- 所有 API Key 通过 .env 管理，禁止写入源码
- LightRAG 使用 Server + REST API 集成，不直接 import
- 模型名称不硬编码在业务逻辑中，通过 ModelRegistry 管理
- 改动范围最小化，不重构未被要求的部分

### API 配置
- LightRAG 调用集中在 `backend/app/services/lightrag_client.py`
- LightRAG base URL 从环境变量 LIGHTRAG_BASE_URL 读取
- LLM API base URL 从环境变量 LLM_BASE_URL 读取

### 模型配置
- 主力模型: step-3.7-flash
- 轻量模型: step-3.5-flash
- Embedding: 本地模型（路径从 EMBEDDING_MODEL_PATH 读取）
- Embedding 模型一旦建立索引，不要随意更换

### 测试规范
- pytest 用于 backend 测试
- 每个 Phase 必须有对应测试且全部通过
- 不允许跳过失败测试直接进入下一 Phase

### Git 规范
- commit message 格式: `类型: 简要描述`
- .env 文件必须在 .gitignore 中
- lightrag/data/ 目录不进 Git
