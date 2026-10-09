from __future__ import annotations

import json
import tempfile
from pathlib import Path

from opc_agent.agent import YouthDocumentAgent
from opc_agent.models import AgentRequest, TaskType, to_serializable


def load_cases(path: str | Path) -> list[dict]:
    cases: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(json.loads(line))
    return cases


def run_eval_dataset(
    dataset_path: str | Path,
    provider=None,
) -> dict:
    cases = load_cases(dataset_path)
    rows: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="opc-agent-eval-") as temp_dir:
        agent = YouthDocumentAgent(provider=provider, output_dir=temp_dir)
        for case in cases:
            run = agent.run(
                AgentRequest(
                    task=TaskType.AUTO,
                    content=case["text"],
                    source=case.get("source", ""),
                )
            )
            serialized = json.dumps(
                to_serializable(run.result),
                ensure_ascii=False,
            ).lower()
            required_terms = [
                str(term).lower() for term in case.get("required_terms", [])
            ]
            task_ok = run.decision.task.value == case["expected_task"]
            terms_ok = all(term in serialized for term in required_terms)
            rows.append(
                {
                    "id": case["id"],
                    "expected_task": case["expected_task"],
                    "actual_task": run.decision.task.value,
                    "task_ok": task_ok,
                    "terms_ok": terms_ok,
                    "passed": task_ok and terms_ok,
                    "confidence": run.decision.confidence,
                }
            )

    passed = sum(1 for row in rows if row["passed"])
    total = len(rows)
    return {
        "passed": passed,
        "total": total,
        "accuracy": round(passed / max(total, 1), 4),
        "rows": rows,
    }

