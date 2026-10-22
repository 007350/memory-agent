# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-22

First public release.

### Added

- **Multi-agent core** — LangGraph workflow routing each query to `knowledge` / `coding` / `vision` / `roadmap` / `diagnosis` / `general`, with keyword fallbacks for intent-critical requests.
- **Graph RAG** — LightRAG server integration over REST (`local` / `global` / `hybrid`), with automatic fallback to plain LLM answers when the server is unavailable.
- **Three-layer memory** — SQLite-backed session memory, long-term user profile, and an event log with feedback and expiry; hybrid scoring of semantic similarity, character-bigram keyword coverage, importance and time decay.
- **Semantic preference de-duplication** — re-phrased preferences collapse into one record; contradictions supersede the old record instead of accumulating.
- **Learning roadmap** — topic extraction → retrieval → validated 5–10 step plan persisted in SQLite, with per-step progress tracking in the UI.
- **Learning diagnosis** — roadmap progress + user profile + recent memory events combined into a strength/weakness report.
- **Self-reflection** — quality gate that retries up to twice and returns to the *originating* agent rather than forcing a knowledge query.
- **Tool use** — `python_repl` and Firecrawl web search, with tool calls rendered in the chat UI.
- **Observability** — request/latency metrics, structured logging middleware, rate limiting.
- **Evaluation** — 30-question end-to-end suite across four question categories.
- **Ops** — cross-platform launchers (`start.bat`, `start.sh`) that auto-detect the interpreter, plus `docker-compose.yml`.
- **Docs** — bilingual README (English / 简体中文), architecture diagram, contributing guide.

### Fixed

- Reflection retries no longer reroute the request to `knowledge`; failures return to the original agent.
- Roadmap and diagnosis intents are no longer misrouted to the knowledge agent, thanks to keyword fallbacks in the router.
- `python_repl` subprocess quoting bug — errors now surface the exception type and stderr instead of a bare "Execution failed".
- Test database isolation: memory tests now allocate a unique `tmp_path` database instead of sharing `.tmp/test_memory.db`, so a failed cleanup can no longer poison later runs.
- `backend/requirements.txt` no longer pulls the LightRAG SDK into the backend (it is only ever called over REST), cutting install time substantially.
- `start.bat` no longer hardcodes an absolute virtualenv path and repository location.

[Unreleased]: https://github.com/007350/memory-agent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/007350/memory-agent/releases/tag/v0.1.0
