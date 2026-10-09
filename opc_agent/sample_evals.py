from __future__ import annotations

import csv
import json
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from opc_agent.agent import YouthDocumentAgent
from opc_agent.fileio import atomic_write_text
from opc_agent.models import AgentRequest, TaskType, to_serializable


MIN_TOTAL_SAMPLES = 20
MIN_SAMPLES_PER_TASK = 5
EVIDENCE_TYPES = ("real", "public", "synthetic")
SUPPORTED_TASKS = {
    TaskType.RESUME,
    TaskType.LETTER,
    TaskType.CONTRACT,
    TaskType.RECEIPT,
}
SUPPORTED_RUN_TASKS = SUPPORTED_TASKS | {TaskType.AUTO}
MANIFEST_COLUMNS = (
    "sample_id",
    "task",
    "path",
    "expected_task",
    "goal_path",
    "baseline_path",
    "evidence_type",
    "consent_confirmed",
    "notes",
)
LOCAL_MANIFEST_RELATIVE_PATH = Path("samples/manifest.local.csv")
TEMPLATE_MANIFEST_RELATIVE_PATH = Path("samples/manifest.csv")


@dataclass(slots=True)
class SampleCase:
    sample_id: str
    task: TaskType
    path: Path
    expected_task: TaskType
    baseline_path: Path
    evidence_type: str
    consent_confirmed: bool
    goal_path: Path | None = None
    notes: str = ""


def default_sample_manifest(project_root: str | Path = ".") -> Path:
    root = Path(project_root)
    local_manifest = root / LOCAL_MANIFEST_RELATIVE_PATH
    if local_manifest.is_file():
        return local_manifest
    return root / TEMPLATE_MANIFEST_RELATIVE_PATH


def validate_sample_manifest(
    manifest_path: str | Path,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    manifest_file = Path(manifest_path).resolve()
    root = _resolve_project_root(manifest_file, project_root)
    rows, columns, issues = _read_manifest_rows(manifest_file)

    missing_columns = [column for column in MANIFEST_COLUMNS if column not in columns]
    if missing_columns:
        issues.append(
            "清单缺少列：" + "、".join(missing_columns)
        )

    sample_ids: set[str] = set()
    task_counts = {task.value: 0 for task in SUPPORTED_TASKS}
    task_counts_by_evidence = {
        evidence_type: {
            task.value: 0 for task in SUPPORTED_TASKS
        }
        for evidence_type in EVIDENCE_TYPES
    }
    evidence_counts = {evidence_type: 0 for evidence_type in EVIDENCE_TYPES}
    valid_rows = 0

    for row_number, row in enumerate(rows, start=2):
        row_issues: list[str] = []
        sample_id = row.get("sample_id", "").strip()
        if not sample_id:
            row_issues.append("sample_id 不能为空")
        elif sample_id in sample_ids:
            row_issues.append(f"sample_id 重复：{sample_id}")
        else:
            sample_ids.add(sample_id)

        task = _parse_task(row.get("task", ""), allow_auto=True)
        expected_task = _parse_task(row.get("expected_task", ""))
        if task is None:
            row_issues.append(
                "task 必须是 auto、resume、letter、contract 或 receipt"
            )
        if expected_task is None:
            row_issues.append(
                "expected_task 必须是 resume、letter、contract 或 receipt"
            )
        evidence_type = row.get("evidence_type", "").strip().lower()
        if evidence_type not in EVIDENCE_TYPES:
            row_issues.append(
                "evidence_type 必须是 real、public 或 synthetic"
            )
        if (
            task is not None
            and task != TaskType.AUTO
            and expected_task is not None
            and task != expected_task
        ):
            row_issues.append(
                "显式指定 task 时必须与 expected_task 一致；"
                "需要验证路由时请把 task 设为 auto"
            )

        sample_path = _resolve_manifest_path(
            root,
            row.get("path", ""),
            row_issues,
            "path",
        )
        baseline_path = _resolve_manifest_path(
            root,
            row.get("baseline_path", ""),
            row_issues,
            "baseline_path",
        )
        goal_value = row.get("goal_path", "").strip()
        goal_path = (
            _resolve_manifest_path(root, goal_value, row_issues, "goal_path")
            if goal_value
            else None
        )

        if sample_path is not None and not sample_path.is_file():
            row_issues.append(f"样本文件不存在：{_display_path(sample_path, root)}")
        if baseline_path is not None:
            _validate_baseline(baseline_path, root, row_issues)
        if goal_path is not None and not goal_path.is_file():
            row_issues.append(f"目标文件不存在：{_display_path(goal_path, root)}")

        if not _parse_bool(row.get("consent_confirmed", "")):
            row_issues.append("consent_confirmed 必须明确为 yes")

        if row_issues:
            for issue in row_issues:
                issues.append(f"第 {row_number} 行：{issue}")
            continue

        valid_rows += 1
        if evidence_type in EVIDENCE_TYPES:
            evidence_counts[evidence_type] += 1
        if expected_task is not None:
            task_counts[expected_task.value] += 1
            if evidence_type in EVIDENCE_TYPES:
                task_counts_by_evidence[evidence_type][
                    expected_task.value
                ] += 1

    missing_by_task = {
        task.value: max(MIN_SAMPLES_PER_TASK - task_counts[task.value], 0)
        for task in sorted(SUPPORTED_TASKS, key=lambda item: item.value)
    }
    real_task_counts = task_counts_by_evidence["real"]
    real_missing_by_task = {
        task.value: max(
            MIN_SAMPLES_PER_TASK - real_task_counts[task.value],
            0,
        )
        for task in sorted(SUPPORTED_TASKS, key=lambda item: item.value)
    }
    ready = (
        not issues
        and evidence_counts["real"] >= MIN_TOTAL_SAMPLES
        and all(
            count >= MIN_SAMPLES_PER_TASK
            for count in real_task_counts.values()
        )
    )
    return {
        "manifest": str(manifest_file),
        "project_root": str(root),
        "issues": issues,
        "schema_ok": not issues,
        "ready": ready,
        "total_rows": len(rows),
        "valid_rows": valid_rows,
        "required_total": MIN_TOTAL_SAMPLES,
        "required_per_task": MIN_SAMPLES_PER_TASK,
        "task_counts": task_counts,
        "task_counts_by_evidence": task_counts_by_evidence,
        "evidence_counts": evidence_counts,
        "missing_by_task": missing_by_task,
        "real_missing_by_task": real_missing_by_task,
    }


def load_sample_manifest(
    manifest_path: str | Path,
    project_root: str | Path | None = None,
) -> list[SampleCase]:
    validation = validate_sample_manifest(manifest_path, project_root)
    if validation["issues"]:
        raise ValueError("样本清单校验失败：" + "；".join(validation["issues"]))

    manifest_file = Path(manifest_path).resolve()
    root = Path(validation["project_root"])
    rows, _, _ = _read_manifest_rows(manifest_file)
    cases: list[SampleCase] = []
    for row in rows:
        goal_value = row.get("goal_path", "").strip()
        cases.append(
            SampleCase(
                sample_id=row["sample_id"].strip(),
                task=TaskType(row["task"].strip()),
                path=(root / row["path"].strip()).resolve(),
                expected_task=TaskType(row["expected_task"].strip()),
                baseline_path=(root / row["baseline_path"].strip()).resolve(),
                evidence_type=row["evidence_type"].strip().lower(),
                consent_confirmed=True,
                goal_path=(
                    (root / goal_value).resolve()
                    if goal_value
                    else None
                ),
                notes=row.get("notes", "").strip(),
            )
        )
    return cases


def run_real_sample_eval(
    manifest_path: str | Path,
    project_root: str | Path | None = None,
    provider=None,
) -> dict[str, Any]:
    validation = validate_sample_manifest(manifest_path, project_root)
    if validation["issues"]:
        raise ValueError("样本清单校验失败：" + "；".join(validation["issues"]))

    cases = load_sample_manifest(manifest_path, project_root)
    if not cases:
        raise ValueError("样本清单中没有可运行的样本。")

    records: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="opc-real-sample-eval-") as temp_dir:
        agent = YouthDocumentAgent(provider=provider, output_dir=temp_dir)
        for case in cases:
            records.append(_run_case(agent, case))

    by_task: dict[str, dict[str, Any]] = {}
    for task in SUPPORTED_TASKS:
        task_records = [
            record for record in records if record["expected_task"] == task.value
        ]
        task_passed = sum(1 for record in task_records if record["passed"])
        by_task[task.value] = {
            "total": len(task_records),
            "passed": task_passed,
            "accuracy": round(task_passed / max(len(task_records), 1), 4),
            "errors": sum(1 for record in task_records if record["error"]),
            "parse_failures": sum(
                1 for record in task_records if not record["parse_ok"]
            ),
            "forbidden_term_hits": sum(
                len(record["forbidden_term_hits"]) for record in task_records
            ),
            "average_seconds": round(
                sum(record["elapsed_seconds"] for record in task_records)
                / max(len(task_records), 1),
                4,
            ),
        }

    by_evidence: dict[str, dict[str, Any]] = {}
    for evidence_type in EVIDENCE_TYPES:
        evidence_records = [
            record
            for record in records
            if record["evidence_type"] == evidence_type
        ]
        evidence_passed = sum(
            1 for record in evidence_records if record["passed"]
        )
        by_evidence[evidence_type] = {
            "total": len(evidence_records),
            "passed": evidence_passed,
            "accuracy": round(
                evidence_passed / max(len(evidence_records), 1),
                4,
            ),
            "parse_failures": sum(
                1 for record in evidence_records if not record["parse_ok"]
            ),
            "run_errors": sum(
                1 for record in evidence_records if record["error"]
            ),
            "route_tests": sum(
                1 for record in evidence_records if record["route_tested"]
            ),
            "route_failures": sum(
                1
                for record in evidence_records
                if record["route_tested"] and not record["route_ok"]
            ),
        }

    real_records = [
        record for record in records if record["evidence_type"] == "real"
    ]
    passed = sum(1 for record in records if record["passed"])
    real_passed = sum(1 for record in real_records if record["passed"])
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "manifest": str(Path(manifest_path).resolve()),
        "ready_for_gate_c": (
            validation["ready"]
            and bool(real_records)
            and real_passed == len(real_records)
        ),
        "total": len(records),
        "passed": passed,
        "accuracy": round(passed / max(len(records), 1), 4),
        "real_total": len(real_records),
        "real_passed": real_passed,
        "real_accuracy": round(
            real_passed / max(len(real_records), 1),
            4,
        ),
        "schema_issues": validation["issues"],
        "task_counts": validation["task_counts"],
        "task_counts_by_evidence": validation["task_counts_by_evidence"],
        "evidence_counts": validation["evidence_counts"],
        "missing_by_task": validation["missing_by_task"],
        "real_missing_by_task": validation["real_missing_by_task"],
        "route_tests": sum(1 for record in records if record["route_tested"]),
        "route_failures": sum(
            1
            for record in records
            if record["route_tested"] and not record["route_ok"]
        ),
        "required_term_failures": sum(
            1 for record in records if not record["required_terms_ok"]
        ),
        "forbidden_term_hits": sum(
            len(record["forbidden_term_hits"]) for record in records
        ),
        "parse_failures": sum(1 for record in records if not record["parse_ok"]),
        "run_errors": sum(1 for record in records if record["error"]),
        "average_seconds": round(
            sum(record["elapsed_seconds"] for record in records)
            / max(len(records), 1),
            4,
        ),
        "by_task": by_task,
        "by_evidence": by_evidence,
        "rows": records,
    }
    return report


def write_real_sample_report(
    report: dict[str, Any],
    reports_dir: str | Path = "reports",
) -> list[str]:
    target_dir = Path(reports_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    json_path = target_dir / "real-sample-report.json"
    markdown_path = target_dir / "real-sample-report.md"
    atomic_write_text(
        json_path,
        json.dumps(report, ensure_ascii=False, indent=2),
    )
    atomic_write_text(
        markdown_path,
        render_real_sample_markdown(report),
    )
    return [str(json_path), str(markdown_path)]


def render_real_sample_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 青年文书智能助手样本评测报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 样本数量：{report['total']}",
        f"- 通过数量：{report['passed']}",
        f"- 总体通过率：{report['accuracy']:.2%}",
        f"- 真实样本数量：{report['real_total']}",
        f"- 真实样本通过：{report['real_passed']}",
        f"- 决策门 C 就绪：{'是' if report['ready_for_gate_c'] else '否'}",
        (
            f"- 自动路由验证：{report['route_tests']}/{report['total']}"
            "（仅 task=auto 计入）"
        ),
        f"- 平均耗时：{report['average_seconds']:.4f} 秒",
        "",
        "## 证据类型",
        "",
        "| 类型 | 样本 | 通过 | 通过率 | 解析失败 | 运行错误 | 路由验证 | 路由失败 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    evidence_labels = {
        "real": "真实用户",
        "public": "公开许可脱敏",
        "synthetic": "项目合成",
    }
    for evidence_type in EVIDENCE_TYPES:
        summary = report["by_evidence"][evidence_type]
        lines.append(
            "| "
            + " | ".join(
                [
                    evidence_labels[evidence_type],
                    str(summary["total"]),
                    str(summary["passed"]),
                    f"{summary['accuracy']:.2%}",
                    str(summary["parse_failures"]),
                    str(summary["run_errors"]),
                    str(summary["route_tests"]),
                    str(summary["route_failures"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
        "## 样本进度",
        "",
        "| 任务 | 已收集 | 每类目标 | 每类缺口 |",
        "| --- | ---: | ---: | ---: |",
        ]
    )
    for task in sorted(report["task_counts"]):
        lines.append(
            "| "
            + " | ".join(
                [
                    task,
                    str(report["task_counts"][task]),
                    str(MIN_SAMPLES_PER_TASK),
                    str(report["missing_by_task"][task]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 质量结果",
            "",
            "| 任务 | 样本 | 通过 | 通过率 | 解析失败 | 运行错误 | 禁止词命中 | 平均耗时 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for task in sorted(report["by_task"]):
        summary = report["by_task"][task]
        lines.append(
            "| "
            + " | ".join(
                [
                    task,
                    str(summary["total"]),
                    str(summary["passed"]),
                    f"{summary['accuracy']:.2%}",
                    str(summary["parse_failures"]),
                    str(summary["errors"]),
                    str(summary["forbidden_term_hits"]),
                    f"{summary['average_seconds']:.4f}",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 样本明细",
            "",
            "| 样本 | 证据 | 任务 | 解析 | 路由 | 必需项 | 禁止词 | 发现项 | 结果 | 耗时 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: |",
        ]
    )
    for row in report["rows"]:
        parse = (
            f"PASS ({row['parser']})"
            if row["parse_ok"]
            else (
                f"FAIL ({row['parser'] or 'unknown'}): "
                + "<br>".join(row["parse_warnings"])
            )
        )
        if not row["route_tested"]:
            route = "N/A（显式指定）"
        elif row["route_ok"]:
            route = f"PASS（{row['actual_task']}）"
        else:
            route = f"{row['actual_task']} != {row['expected_task']}"
        required = "PASS" if row["required_terms_ok"] else (
            "缺少 " + "、".join(row["required_terms_missing"])
        )
        forbidden = (
            "无"
            if not row["forbidden_term_hits"]
            else "命中 " + "、".join(row["forbidden_term_hits"])
        )
        findings = (
            f"{row['finding_coverage']['matched']}/"
            f"{row['finding_coverage']['expected']}"
        )
        result = "PASS" if row["passed"] else "FAIL"
        if row["error"]:
            result = f"ERROR: {row['error']}"
        lines.append(
            "| "
            + " | ".join(
                _escape_table(str(value))
                for value in (
                    row["sample_id"],
                    row["evidence_type"],
                    row["expected_task"],
                    parse,
                    route,
                    required,
                    forbidden,
                    findings,
                    result,
                    f"{row['elapsed_seconds']:.4f}",
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 本报告只用于内部质量验证，不保存样本正文。",
            "- 只有 `evidence_type=real` 的样本计入决策门 C。",
            "- `public` 和 `synthetic` 样本只用于技术回归，不代表真实用户需求或质量结论。",
            "- `forbidden_terms` 只能发现已明确定义的事实编造风险，仍需人工复核。",
            "- 达到样本数量不等于通过决策门 C，所有样本必须通过且无严重事实错误。",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _run_case(agent: YouthDocumentAgent, case: SampleCase) -> dict[str, Any]:
    baseline = json.loads(case.baseline_path.read_text(encoding="utf-8"))
    goal = (
        case.goal_path.read_text(encoding="utf-8")
        if case.goal_path is not None
        else str(baseline.get("goal", ""))
    )
    started = time.perf_counter()
    try:
        run = agent.run_file(
            path=case.path,
            task=case.task,
            goal=goal,
        )
        elapsed = time.perf_counter() - started
        serialized = json.dumps(
            to_serializable(run.result),
            ensure_ascii=False,
        ).lower()
        required_terms = _string_list(baseline.get("required_terms", []))
        forbidden_terms = _string_list(baseline.get("forbidden_terms", []))
        expected_findings = _string_list(
            baseline.get("expected_finding_titles", [])
        )
        missing_required = [
            term for term in required_terms if term.lower() not in serialized
        ]
        forbidden_hits = [
            term for term in forbidden_terms if term.lower() in serialized
        ]
        finding_text = "\n".join(
            finding.title.lower() for finding in run.result.findings
        )
        matched_findings = [
            term for term in expected_findings if term.lower() in finding_text
        ]
        min_findings = int(baseline.get("min_findings", 0) or 0)
        finding_ok = (
            len(matched_findings) == len(expected_findings)
            and len(run.result.findings) >= min_findings
        )
        route_ok = run.decision.task == case.expected_task
        route_tested = case.task == TaskType.AUTO
        required_terms_ok = not missing_required
        parse_ok = not run.parse_warnings
        passed = (
            parse_ok
            and
            route_ok
            and required_terms_ok
            and not forbidden_hits
            and finding_ok
        )
        return {
            "sample_id": case.sample_id,
            "evidence_type": case.evidence_type,
            "expected_task": case.expected_task.value,
            "actual_task": run.decision.task.value,
            "parser": run.parser,
            "parse_ok": parse_ok,
            "parse_warnings": run.parse_warnings,
            "route_tested": route_tested,
            "route_ok": route_ok,
            "required_terms_ok": required_terms_ok,
            "required_terms_missing": missing_required,
            "forbidden_term_hits": forbidden_hits,
            "finding_coverage": {
                "matched": len(matched_findings),
                "expected": len(expected_findings),
                "matched_titles": matched_findings,
            },
            "min_findings": min_findings,
            "finding_count": len(run.result.findings),
            "passed": passed,
            "confidence": run.decision.confidence,
            "elapsed_seconds": round(elapsed, 4),
            "error": "",
        }
    except Exception as exc:
        return {
            "sample_id": case.sample_id,
            "evidence_type": case.evidence_type,
            "expected_task": case.expected_task.value,
            "actual_task": "",
            "parser": "",
            "parse_ok": False,
            "parse_warnings": [],
            "route_tested": False,
            "route_ok": False,
            "required_terms_ok": False,
            "required_terms_missing": [],
            "forbidden_term_hits": [],
            "finding_coverage": {
                "matched": 0,
                "expected": 0,
                "matched_titles": [],
            },
            "min_findings": 0,
            "finding_count": 0,
            "passed": False,
            "confidence": 0.0,
            "elapsed_seconds": round(time.perf_counter() - started, 4),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _read_manifest_rows(
    manifest_path: Path,
) -> tuple[list[dict[str, str]], list[str], list[str]]:
    if not manifest_path.is_file():
        raise FileNotFoundError(f"样本清单不存在：{manifest_path}")
    issues: list[str] = []
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = [
            {key: (value or "").strip() for key, value in row.items()}
            for row in reader
            if any((value or "").strip() for value in row.values())
        ]
    return rows, columns, issues


def _resolve_project_root(
    manifest_path: Path,
    project_root: str | Path | None,
) -> Path:
    if project_root is not None:
        return Path(project_root).resolve()
    for parent in manifest_path.parents:
        if parent.name == "samples":
            return parent.parent.resolve()
    return manifest_path.parent.resolve()


def _resolve_manifest_path(
    root: Path,
    value: str,
    issues: list[str],
    label: str,
) -> Path | None:
    if not value:
        issues.append(f"{label} 不能为空")
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        issues.append(f"{label} 必须使用项目内相对路径")
        return None
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        issues.append(f"{label} 不能指向项目目录之外")
        return None
    return resolved


def _validate_baseline(path: Path, root: Path, issues: list[str]) -> None:
    if not path.is_file():
        issues.append(f"人工基线不存在：{_display_path(path, root)}")
        return
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(f"人工基线不是有效 JSON：{path.name}（{exc.msg}）")
        return
    if not isinstance(baseline, dict):
        issues.append(f"人工基线必须是 JSON 对象：{path.name}")
        return
    for key in ("required_terms", "forbidden_terms", "expected_finding_titles"):
        value = baseline.get(key, [])
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            issues.append(f"人工基线 {path.name} 的 {key} 必须是字符串数组")
    min_findings = baseline.get("min_findings", 0)
    if not isinstance(min_findings, int) or min_findings < 0:
        issues.append(f"人工基线 {path.name} 的 min_findings 必须是非负整数")
    goal = baseline.get("goal", "")
    if not isinstance(goal, str):
        issues.append(f"人工基线 {path.name} 的 goal 必须是字符串")


def _parse_task(
    value: str,
    *,
    allow_auto: bool = False,
) -> TaskType | None:
    try:
        task = TaskType(value.strip())
    except ValueError:
        return None
    if allow_auto and task == TaskType.AUTO:
        return task
    if task not in SUPPORTED_TASKS:
        return None
    return task


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "是"}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")
