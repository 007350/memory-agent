# Contributing

Thanks for taking a look. This is a small project, so the bar is simple: **keep it honest and keep tests green.**

## Setup

```bash
git clone https://github.com/007350/memory-agent.git
cd memory-agent
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
pip install "lightrag-hku[api]==1.5.6"   # only needed to run the full stack
cd frontend && npm install && cd ..
```

Copy `backend/.env.example` → `backend/.env` and fill in your keys. The unit tests do **not** need real keys or a running LightRAG server.

## Before you open a PR

```bash
cd backend
python -m pytest tests/ --ignore=tests/evaluation -q   # must be all green
python -c "import app.main"                            # the app must still boot
```

The second command matters: unit tests import individual modules, so a broken import in `app/main.py` or a missing dependency can pass every test while making the app unrunnable. CI runs an "import every module" smoke test for exactly this reason.

Frontend changes:

```bash
cd frontend && npm run lint && npm run build
```

## Conventions

| Area | Rule |
|---|---|
| Secrets | Only via env vars. Never commit `.env`, keys, `memory.db`, `lightrag/data/`. Add new settings to `.env.example` **and** `app/config.py`. |
| Model names | Never hardcode. Resolve through `services/model_registry.py`. |
| LightRAG | Always via `services/lightrag_client.py` (REST). Do not `import lightrag` in `app/`. |
| Degradation | New external calls need a fallback path. Log a warning and degrade; don't raise into the user's face. |
| Scope | Fix what the issue is about. Refactors of unrelated code belong in their own PR. |
| Tests | Every behaviour change needs a test. DB tests must use `tmp_path` — never a shared fixed path. |
| Commits | `type: short description` — `feat` / `fix` / `docs` / `test` / `refactor` / `chore`. |

## Adding an agent

1. Create `backend/app/agents/<name>_agent.py` with the same async signature as the existing agents.
2. Register the intent in `backend/app/agents/router.py` — add it to the routing prompt **and** to the keyword fallback if misrouting would be expensive.
3. Wire the node into `backend/app/graph/workflow.py` (node, edge, and the reflection conditional map — forgetting the last one silently breaks retries).
4. Add a unit test in `backend/tests/` with the LLM mocked.
5. Document it in both `README.md` and `README.zh-CN.md`.

## Adding a tool

Subclass `app/tools/base.py:BaseTool`, declare `name` / `description` / `parameters` (JSON Schema), implement `execute`, and raise `ToolExecutionError` for expected failures. Register it where the agents construct their tool list.

## Reporting bugs

Open an issue with a minimal reproduction: the request, the observed output, and what you expected. Logs from the backend window are worth more than a description.

## License

By contributing you agree your work is released under the [MIT License](LICENSE).
