from __future__ import annotations

from abc import ABC, abstractmethod

from opc_agent.models import AgentRequest, TaskType, WorkflowResult
from opc_agent.providers.base import ModelProvider, ProviderError, extract_json


class Workflow(ABC):
    task: TaskType

    @abstractmethod
    def run(
        self,
        request: AgentRequest,
        provider: ModelProvider,
    ) -> WorkflowResult:
        raise NotImplementedError

    def model_json(
        self,
        provider: ModelProvider,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[dict | None, str | None]:
        if provider.is_mock:
            return None, None
        try:
            raw = provider.complete(system_prompt, user_prompt)
        except ProviderError as exc:
            return None, f"模型调用失败，已使用本地规则：{exc}"
        data = extract_json(raw)
        if data is None:
            return None, "模型没有返回有效 JSON，已使用本地规则。"
        return data, None

