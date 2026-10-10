from opc_agent.providers.base import ModelProvider, ProviderError, extract_json
from opc_agent.providers.deepseek import DeepSeekProvider
from opc_agent.providers.mock import MockProvider
from opc_agent.providers.openai_compatible import OpenAICompatibleProvider
from opc_agent.providers.openai_responses import OpenAIResponsesProvider


def create_provider(
    provider_name: str,
    model: str = "",
    api_key: str = "",
    base_url: str = "",
    max_tokens: int = 0,
    temperature: float = 0.2,
    timeout_seconds: int = 45,
) -> ModelProvider:
    name = provider_name.strip().lower()
    if name == "mock":
        return MockProvider()
    if name == "deepseek":
        return DeepSeekProvider(
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )
    if name == "openai":
        return OpenAIResponsesProvider(model=model, api_key=api_key)
    if name == "openai-compatible":
        return OpenAICompatibleProvider(
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )
    raise ProviderError(f"不支持的 Provider：{provider_name}")


__all__ = [
    "DeepSeekProvider",
    "MockProvider",
    "ModelProvider",
    "OpenAICompatibleProvider",
    "OpenAIResponsesProvider",
    "ProviderError",
    "create_provider",
    "extract_json",
]

