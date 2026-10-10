from __future__ import annotations

from opc_agent.providers.base import ModelProvider, ProviderError


class OpenAICompatibleProvider(ModelProvider):
    """Provider for services exposing an OpenAI-compatible chat API."""

    name = "openai-compatible"

    def __init__(
        self,
        model: str,
        api_key: str = "",
        base_url: str = "",
        max_tokens: int = 0,
        temperature: float = 0.2,
        timeout_seconds: int = 45,
    ) -> None:
        if not model.strip():
            raise ProviderError("OpenAI-compatible provider requires OPC_MODEL.")
        self.model = model.strip()
        self.api_key = api_key.strip()
        self.base_url = base_url.strip()
        self.max_tokens = max(0, int(max_tokens))
        self.temperature = max(0.0, min(2.0, float(temperature)))
        self.timeout_seconds = max(5, int(timeout_seconds))

    @property
    def available(self) -> bool:
        if not (self.api_key or self.base_url):
            return False
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return True

    def complete(self, system_prompt: str, user_prompt: str) -> str | None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError(
                'Install the OpenAI client with: pip install -e ".[openai]"'
            ) from exc

        client = OpenAI(
            api_key=self.api_key or "not-needed",
            base_url=self.base_url or None,
            timeout=self.timeout_seconds,
        )
        parameters: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
        }
        if self.max_tokens > 0:
            parameters["max_tokens"] = self.max_tokens
        try:
            response = client.chat.completions.create(**parameters)
        except Exception as exc:
            raise ProviderError(
                f"模型接口调用失败：{type(exc).__name__}: {exc}"
            ) from exc

        choices = getattr(response, "choices", None)
        if not choices:
            raise ProviderError("模型接口没有返回候选结果。")
        content = getattr(getattr(choices[0], "message", None), "content", None)
        if isinstance(content, str) and content.strip():
            return content
        raise ProviderError("模型接口没有返回文本内容。")
