from dataclasses import dataclass, field
from enum import Enum


class ModelCapability(str, Enum):
    CHAT = "chat"
    REASONING = "reasoning"
    CODING = "coding"
    VISION = "vision"
    TOOL_CALLING = "tool_calling"


@dataclass
class ModelConfig:
    name: str
    provider: str
    base_url: str
    api_key_env: str
    capabilities: set[ModelCapability] = field(default_factory=set)
    context_window: int = 32768
    is_default: bool = False


class ModelRegistry:
    _registry: dict[str, ModelConfig] = {}

    @classmethod
    def register(cls, config: ModelConfig) -> None:
        cls._registry[config.name] = config

    @classmethod
    def get(cls, name: str) -> ModelConfig:
        if name not in cls._registry:
            raise KeyError(f"Model '{name}' not found in registry")
        return cls._registry[name]

    @classmethod
    def default(cls) -> ModelConfig:
        for cfg in cls._registry.values():
            if cfg.is_default:
                return cfg
        raise RuntimeError("No default model registered")

    @classmethod
    def find_by_capability(cls, *caps: ModelCapability) -> list[ModelConfig]:
        required = set(caps)
        return [c for c in cls._registry.values() if required.issubset(c.capabilities)]

    @classmethod
    def all(cls) -> dict[str, ModelConfig]:
        return dict(cls._registry)
