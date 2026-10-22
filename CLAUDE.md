# CLAUDE.md — 工程约定

给 AI 编码助手（Claude Code / Codex / Cursor 等）和人类贡献者看的项目约定。
动手改代码前请先读一遍。

## 项目是什么

面向 AI / CS 学习与代码辅助的多 Agent 知识助手，技术栈：

- **后端** FastAPI + LangGraph（`backend/app`）
- **RAG** LightRAG Server，只通过 REST 调用（`backend/app/services/lightrag_client.py`），主应用不 import SDK
- **前端** React 19 + TypeScript + Vite（`frontend/src`）
- **记忆** SQLite（aiosqlite），三层：会话记忆 / 用户画像 / 记忆事件

## 硬约束

1. **密钥只走环境变量**。禁止在源码里写死 API Key、base URL、token；新增配置项同时更新 `backend/.env.example`。
2. **模型名不硬编码**。统一从 `services/model_registry.py` 取，不信任 LLM 自己填的模型名。
3. **LightRAG 保持进程外调用**。不要在 `app/` 里 `import lightrag`。
4. **降级优先于崩溃**。LightRAG / Embedding 不可用时退化为纯 LLM 或关键词检索，并记 warning。
5. **改动范围最小化**。不重构没被要求的部分，不动与本任务无关的文件。

## 代码结构

```
backend/app/
  main.py            FastAPI 装配：中间件、路由、生命周期
  config.py          pydantic-settings，只读 env
  graph/             LangGraph：state.py / nodes.py / workflow.py
  agents/            router + 6 个 agent（knowledge/coding/vision/roadmap/diagnosis/general）
  services/          lightrag_client / memory_service / embedding_service / model_registry
  tools/             python_repl、web_search
  routes/            chat / documents / memory / roadmap / health / metrics
  middleware/        logging / metrics / rate_limit
```

工作流：`memory_retrieval → router → <agent> → reflection → memory_update`。
reflection 失败会回到**原 agent** 重试（最多 2 次），不会强行改路由。

## 测试

```bash
cd backend
python -m pytest tests/ --ignore=tests/evaluation -q    # 单元测试，不触网
python -m pytest tests/ -m integration                  # 需要 LightRAG 在 9621 运行
```

- 测试**不触网**：LLM / HTTP 一律 mock，Embedding 用 fixture 关掉。
- 数据库测试用 `tmp_path` 分配独立库文件，**不要**共用固定路径（残留数据会导致串扰）。
- 新增功能必须带测试，且不能跳过失败用例进入下一步。

## Git

- commit message：`类型: 简要描述`（feat / fix / docs / test / refactor / chore）
- `.env`、`memory.db`、`lightrag/data/`、本地 AI 助手目录一律不进 Git
