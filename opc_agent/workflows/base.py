from __future__ import annotations

import sys
from abc import ABC, abstractmethod

from opc_agent.models import AgentRequest, TaskType, WorkflowResult
from opc_agent.providers.base import ModelProvider, ProviderError, extract_json


PROVIDER_MAINTENANCE_MESSAGE = (
    "后台在线服务正在维护，已使用本地规则完成处理，"
    "请稍后再试在线功能。"
)


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
            print(f"Provider call failed: {exc}", file=sys.stderr)
            return None, PROVIDER_MAINTENANCE_MESSAGE
        data = extract_json(raw)
        if data is None:
            return None, "模型没有返回有效 JSON，已使用本地规则。"
        return data, None

