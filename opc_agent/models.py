from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    AUTO = "auto"
    RESUME = "resume"
    LETTER = "letter"
    CONTRACT = "contract"
    RECEIPT = "receipt"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class AgentRequest:
    task: TaskType
    content: str
    source: str = ""
    goal: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TaskDecision:
    task: TaskType
    confidence: float
    scores: dict[str, int]
    reason: str


@dataclass(slots=True)
class Finding:
    title: str
    severity: str
    detail: str
    evidence: str = ""
    suggestion: str = ""


@dataclass(slots=True)
class OutputArtifact:
    name: str
    media_type: str
    content: str


@dataclass(slots=True)
class WorkflowResult:
    task: TaskType
    summary: str
    data: dict[str, Any]
    findings: list[Finding] = field(default_factory=list)
    artifacts: list[OutputArtifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass(slots=True)
class AgentRun:
    decision: TaskDecision
    result: WorkflowResult
    output_files: list[str] = field(default_factory=list)
    provider: str = "mock"
    parser: str = ""
    parse_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


def to_serializable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): to_serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_serializable(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            key: to_serializable(item)
            for key, item in asdict(value).items()
        }
    return value
