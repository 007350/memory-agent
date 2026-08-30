import os
from app.services.model_registry import ModelRegistry, ModelConfig, ModelCapability


def init_registry() -> None:
    base_url = os.environ.get("LLM_BASE_URL", "https://api.stepfun.com/step_plan/v1")
    main_model = os.environ.get("LLM_MODEL_MAIN", "step-3.7-flash")
    light_model = os.environ.get("LLM_MODEL_LIGHT", "step-3.5-flash")

    ModelRegistry.register(ModelConfig(
        name=main_model,
        provider=os.environ.get("LLM_PROVIDER", "stepfun"),
        base_url=base_url,
        api_key_env="LLM_API_KEY",
        capabilities={
            ModelCapability.CHAT,
            ModelCapability.REASONING,
            ModelCapability.CODING,
            ModelCapability.TOOL_CALLING,
        },
        context_window=32768,
        is_default=True,
    ))
    ModelRegistry.register(ModelConfig(
        name=light_model,
        provider=os.environ.get("LLM_PROVIDER", "stepfun"),
        base_url=base_url,
        api_key_env="LLM_API_KEY",
        capabilities={
            ModelCapability.CHAT,
            ModelCapability.CODING,
        },
        context_window=16384,
        is_default=False,
    ))
