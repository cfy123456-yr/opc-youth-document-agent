from __future__ import annotations

from opc_agent.providers.base import ModelProvider


class MockProvider(ModelProvider):
    name = "mock"

    @property
    def is_mock(self) -> bool:
        return True

    @property
    def available(self) -> bool:
        return True

    def complete(self, system_prompt: str, user_prompt: str) -> str | None:
        return None

