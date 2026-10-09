from __future__ import annotations

from opc_agent.providers.base import ModelProvider, ProviderError


class OpenAIResponsesProvider(ModelProvider):
    """Small adapter kept behind an optional dependency.

    The official documentation site was unreachable from the build environment,
    so the live adapter is intentionally thin and is not exercised by tests.
    """

    name = "openai"

    def __init__(self, model: str, api_key: str | None = None) -> None:
        if not model:
            raise ProviderError("OpenAI provider requires OPC_MODEL or --model.")
        self.model = model
        self.api_key = api_key

    @property
    def available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return True

    def complete(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is not set.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError(
                'Install the OpenAI adapter with: pip install -e ".[openai]"'
            ) from exc

        client = OpenAI(api_key=self.api_key)
        response = client.responses.create(
            model=self.model,
            instructions=system_prompt,
            input=user_prompt,
        )
        output_text = getattr(response, "output_text", None)
        if output_text:
            return output_text
        raise ProviderError("The model response did not contain output_text.")
