from __future__ import annotations

from datetime import datetime
from pathlib import Path

from opc_agent.artifacts import build_artifacts, write_artifacts
from opc_agent.models import AgentRequest, AgentRun, TaskDecision, TaskType
from opc_agent.parsers import parse_document
from opc_agent.providers.base import ModelProvider
from opc_agent.providers.mock import MockProvider
from opc_agent.router import route_task
from opc_agent.workflows import (
    ContractWorkflow,
    LetterWorkflow,
    ReceiptWorkflow,
    ResumeWorkflow,
)
from opc_agent.workflows.base import Workflow


class YouthDocumentAgent:
    def __init__(
        self,
        provider: ModelProvider | None = None,
        output_dir: str | Path = "outputs",
    ) -> None:
        self.provider = provider or MockProvider()
        self.output_dir = Path(output_dir)
        self.workflows: dict[TaskType, Workflow] = {
            TaskType.RESUME: ResumeWorkflow(),
            TaskType.LETTER: LetterWorkflow(),
            TaskType.CONTRACT: ContractWorkflow(),
            TaskType.RECEIPT: ReceiptWorkflow(),
        }

    def run(
        self,
        request: AgentRequest,
        warnings: list[str] | None = None,
        parser: str = "",
    ) -> AgentRun:
        decision = self.route(request)
        if decision.task == TaskType.UNKNOWN:
            raise ValueError(
                "无法识别任务类型。请使用 --task 指定 "
                "resume、letter、contract 或 receipt。"
            )

        workflow = self.workflows[decision.task]
        result = workflow.run(request, self.provider)
        parse_warnings = list(warnings or [])
        if parse_warnings:
            result.warnings.extend(parse_warnings)
        artifacts = build_artifacts(result, decision)
        run_id = self._run_id(decision.task)
        output_files = write_artifacts(self.output_dir, run_id, artifacts)
        return AgentRun(
            decision=decision,
            result=result,
            output_files=output_files,
            provider=self.provider.name,
            parser=parser,
            parse_warnings=parse_warnings,
        )

    def run_file(
        self,
        path: str | Path,
        task: TaskType = TaskType.AUTO,
        goal: str = "",
        context: dict | None = None,
        options: dict | None = None,
    ) -> AgentRun:
        parsed = parse_document(path)
        request = AgentRequest(
            task=task,
            content=parsed.text,
            source=parsed.source,
            goal=goal,
            context=context or {},
            options=options or {},
        )
        return self.run(
            request,
            warnings=parsed.warnings,
            parser=parsed.parser,
        )

    def route(self, request: AgentRequest) -> TaskDecision:
        if request.task != TaskType.AUTO:
            return TaskDecision(
                task=request.task,
                confidence=1.0,
                scores={request.task.value: 1},
                reason="用户显式指定任务类型。",
            )
        return route_task(request.content, request.source)

    @staticmethod
    def _run_id(task: TaskType) -> str:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        return f"{stamp}-{task.value}"
