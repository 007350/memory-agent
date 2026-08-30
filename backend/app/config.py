import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    llm_base_url: str = os.environ.get("LLM_BASE_URL", "https://api.stepfun.com/step_plan/v1")
    llm_api_key: str = os.environ.get("LLM_API_KEY", "")
    llm_model_main: str = os.environ.get("LLM_MODEL_MAIN", "step-3.7-flash")
    llm_model_light: str = os.environ.get("LLM_MODEL_LIGHT", "step-3.5-flash")

    # LightRAG
    lightrag_base_url: str = os.environ.get("LIGHTRAG_BASE_URL", "http://localhost:9621")
    lightrag_api_key: str = os.environ.get("LIGHTRAG_API_KEY", "")

    # Firecrawl
    firecrawl_api_key: str = os.environ.get("FIRECRAWL_API_KEY", "")
    firecrawl_base_url: str = os.environ.get("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev/v1")

    # Embedding（OpenAI 兼容接口，用于记忆语义检索）
    embedding_base_url: str = os.environ.get("EMBEDDING_BASE_URL", "")
    embedding_api_key: str = os.environ.get("EMBEDDING_API_KEY", "")
    embedding_model: str = os.environ.get("EMBEDDING_MODEL", "")
    embedding_dim: int = int(os.environ.get("EMBEDDING_DIM", "0") or 0)

    # Memory
    memory_semantic_top_k: int = int(os.environ.get("MEMORY_SEMANTIC_TOP_K", "20"))
    memory_decay_half_life_days: float = float(os.environ.get("MEMORY_DECAY_HALF_LIFE_DAYS", "14"))
    memory_context_budget_chars: int = int(os.environ.get("MEMORY_CONTEXT_BUDGET_CHARS", "3000"))
    memory_event_snippet_chars: int = int(os.environ.get("MEMORY_EVENT_SNIPPET_CHARS", "200"))

    cors_origins: list[str] = [
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
        "http://localhost:5175", "http://127.0.0.1:5175",
    ]
    chat_query_max_length: int = 4000
    memory_limit_max: int = 200
    rate_limit_max_requests: int = 60

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
