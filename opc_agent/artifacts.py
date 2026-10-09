from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from opc_agent.fileio import atomic_write_text
from opc_agent.models import OutputArtifact, TaskDecision, WorkflowResult, to_serializable


def build_artifacts(
    result: WorkflowResult,
    decision: TaskDecision,
) -> list[OutputArtifact]:
    report = render_markdown(result, decision)
    artifacts = [
        OutputArtifact(
            name="report.md",
            media_type="text/markdown",
            content=report,
        ),
        OutputArtifact(
            name="result.json",
            media_type="application/json",
            content=json.dumps(
                to_serializable(result),
                ensure_ascii=False,
                indent=2,
            ),
        ),
    ]
    if result.task.value == "receipt":
        artifacts.append(
            OutputArtifact(
                name="receipts.csv",
                media_type="text/csv",
                content=render_receipt_csv(result),
            )
        )
    return artifacts


def render_markdown(result: WorkflowResult, decision: TaskDecision) -> str:
    lines = [
        "# 青年文书智能助手处理报告",
        "",
        f"- 任务类型：`{result.task.value}`",
        f"- 路由置信度：`{decision.confidence:.2f}`",
        f"- 结果置信度：`{result.confidence:.2f}`",
        f"- 路由说明：{decision.reason}",
        "",
        "## 处理摘要",
        "",
        result.summary,
        "",
        "## 发现与建议",
        "",
    ]

    if result.findings:
        lines.extend(
            [
                "| 严重度 | 问题 | 说明 | 证据 | 建议 |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for finding in result.findings:
            lines.append(
                "| "
                + " | ".join(
                    _escape_table(value)
                    for value in (
                        finding.severity,
                        finding.title,
                        finding.detail,
                        finding.evidence,
                        finding.suggestion,
                    )
                )
                + " |"
            )
    else:
        lines.append("未发现需要单独列出的风险项。")

    lines.extend(
        [
            "",
            "## 结构化结果",
            "",
            "```json",
            json.dumps(result.data, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )

    if result.warnings:
        lines.extend(["## 运行提示", ""])
        lines.extend(f"- {warning}" for warning in result.warnings)
        lines.append("")

    lines.extend(
        [
            "## 使用边界",
            "",
            "- 结果需要用户确认后才能对外提交。",
            "- 系统不得编造用户未提供的经历、数据、证书或法律依据。",
            "- 合同结果仅用于辅助理解，不构成法律意见。",
            "- 票据结果需要使用原始票据进行最终核对。",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def render_receipt_csv(result: WorkflowResult) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["商家", "日期", "金额", "类别", "需要确认", "原文"])
    for item in result.data.get("items", []):
        writer.writerow(
            [
                item.get("merchant", ""),
                item.get("date", ""),
                item.get("amount", ""),
                item.get("category", ""),
                "是" if item.get("needs_confirmation") else "否",
                item.get("evidence", ""),
            ]
        )
    writer.writerow([])
    writer.writerow(["合计", "", result.data.get("total", 0), "", "", ""])
    return output.getvalue()


def write_artifacts(
    output_dir: str | Path,
    run_id: str,
    artifacts: list[OutputArtifact],
) -> list[str]:
    target_dir = Path(output_dir) / run_id
    target_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for artifact in artifacts:
        target = target_dir / artifact.name
        atomic_write_text(target, artifact.content)
        paths.append(str(target))
    return paths


def _escape_table(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")
