from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from opc_agent.agent import YouthDocumentAgent
from opc_agent.config import Settings
from opc_agent.console import configure_stdio
from opc_agent.evals import run_eval_dataset
from opc_agent.models import AgentRequest, TaskType, to_serializable
from opc_agent.providers import (
    MockProvider,
    OpenAIResponsesProvider,
    ProviderError,
)
from opc_agent.router import route_task
from opc_agent.sample_evals import (
    default_sample_manifest,
    run_real_sample_eval,
    validate_sample_manifest,
    write_real_sample_report,
)


def build_parser() -> argparse.ArgumentParser:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(
        prog="opc-agent",
        description="青年文书智能助手本地 CLI。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="检查运行环境。")
    doctor.set_defaults(handler=command_doctor)

    route = subparsers.add_parser("route", help="仅识别任务类型。")
    route.add_argument("--text", required=True, help="待识别文本。")
    route.add_argument("--source", default="", help="文件名或来源。")
    route.set_defaults(handler=command_route)

    run = subparsers.add_parser("run", help="运行文书 Agent。")
    input_group = run.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", help="输入文件路径。")
    input_group.add_argument("--text", help="直接传入文本。")
    run.add_argument(
        "--task",
        choices=[task.value for task in TaskType],
        default=TaskType.AUTO.value,
    )
    run.add_argument("--goal", default="", help="目标岗位或目标说明。")
    run.add_argument("--goal-file", default="", help="目标岗位或目标说明文件。")
    run.add_argument(
        "--provider",
        choices=("mock", "openai"),
        default=settings.provider,
    )
    run.add_argument("--model", default=settings.model)
    run.add_argument(
        "--output-dir",
        default=settings.output_dir,
    )
    run.add_argument("--json", action="store_true", help="输出完整 JSON。")
    run.set_defaults(handler=command_run)

    evaluate = subparsers.add_parser("eval", help="运行离线评测。")
    evaluate.add_argument(
        "--dataset",
        default="evals/cases.jsonl",
        help="JSONL 评测集。",
    )
    evaluate.add_argument("--json", action="store_true")
    evaluate.set_defaults(handler=command_eval)

    samples = subparsers.add_parser("samples", help="管理样本回归和真实样本验收。")
    sample_commands = samples.add_subparsers(
        dest="samples_command",
        required=True,
    )

    sample_validate = sample_commands.add_parser(
        "validate",
        help="校验样本清单、证据类型、文件路径和人工基线。",
    )
    sample_validate.add_argument(
        "--manifest",
        default=str(default_sample_manifest()),
        help="样本清单路径。",
    )
    sample_validate.add_argument(
        "--project-root",
        default="",
        help="清单相对路径的根目录，默认自动推断。",
    )
    sample_validate.add_argument("--json", action="store_true")
    sample_validate.set_defaults(handler=command_samples_validate)

    sample_eval = sample_commands.add_parser(
        "eval",
        help="运行样本并通过 Markdown/JSON 报告输出结果。",
    )
    sample_eval.add_argument(
        "--manifest",
        default=str(default_sample_manifest()),
        help="样本清单路径。",
    )
    sample_eval.add_argument(
        "--project-root",
        default="",
        help="清单相对路径的根目录，默认自动推断。",
    )
    sample_eval.add_argument(
        "--reports-dir",
        default="reports",
        help="报告输出目录。",
    )
    sample_eval.add_argument("--json", action="store_true")
    sample_eval.set_defaults(handler=command_samples_eval)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (ValueError, RuntimeError, ProviderError, FileNotFoundError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


def command_doctor(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    checks = {
        "python": sys.version.split()[0],
        "provider": settings.provider,
        "openai_api_key": settings.has_openai_api_key,
        "openai_package": _module_available("openai"),
        "markitdown": _module_available("markitdown"),
        "python_docx": _module_available("docx"),
        "pypdf": _module_available("pypdf"),
        "paddleocr": _module_available("paddleocr"),
    }
    for key, value in checks.items():
        print(f"{key}: {value}")
    return 0


def command_route(args: argparse.Namespace) -> int:
    decision = route_task(args.text, args.source)
    print(json.dumps(to_serializable(decision), ensure_ascii=False, indent=2))
    return 0


def command_run(args: argparse.Namespace) -> int:
    provider = _build_provider(args)
    agent = YouthDocumentAgent(provider=provider, output_dir=args.output_dir)
    goal = _read_goal(args.goal, args.goal_file)
    task = TaskType(args.task)

    if args.input:
        run = agent.run_file(
            path=args.input,
            task=task,
            goal=goal,
        )
    else:
        run = agent.run(
            AgentRequest(
                task=task,
                content=args.text,
                goal=goal,
            )
        )

    if args.json:
        print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
        return 0

    print(f"任务：{run.result.task.value}")
    print(f"Provider：{run.provider}")
    print(f"路由置信度：{run.decision.confidence:.2f}")
    print(f"结果置信度：{run.result.confidence:.2f}")
    print(f"摘要：{run.result.summary}")
    if run.result.findings:
        print("\n主要发现：")
        for finding in run.result.findings[:10]:
            print(
                f"- [{finding.severity}] {finding.title}: "
                f"{finding.suggestion or finding.detail}"
            )
    if run.result.warnings:
        print("\n运行提示：")
        for warning in run.result.warnings:
            print(f"- {warning}")
    print("\n输出文件：")
    for path in run.output_files:
        print(f"- {path}")
    return 0


def command_eval(args: argparse.Namespace) -> int:
    report = run_eval_dataset(args.dataset, provider=MockProvider())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["passed"] == report["total"] else 1

    print(
        f"评测通过：{report['passed']}/{report['total']}，"
        f"准确率：{report['accuracy']:.2%}"
    )
    for row in report["rows"]:
        status = "PASS" if row["passed"] else "FAIL"
        print(
            f"- {status} {row['id']} "
            f"expected={row['expected_task']} actual={row['actual_task']}"
        )
    return 0 if report["passed"] == report["total"] else 1


def command_samples_validate(args: argparse.Namespace) -> int:
    report = validate_sample_manifest(
        args.manifest,
        project_root=args.project_root or None,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        status = "真实样本已就绪" if report["ready"] else "真实样本仍在收集"
        print(
            f"样本清单：{report['valid_rows']}/{report['total_rows']} 行有效，"
            f"状态：{status}"
        )
        print(
            "证据类型："
            + "，".join(
                f"{evidence_type}={count}"
                for evidence_type, count in report["evidence_counts"].items()
            )
        )
        print(
            "样本进度："
            + "，".join(
                f"{task}={count}"
                for task, count in report["task_counts"].items()
            )
        )
        if report["issues"]:
            print("问题：")
            for issue in report["issues"]:
                print(f"- {issue}")
    return 0 if report["schema_ok"] else 1


def command_samples_eval(args: argparse.Namespace) -> int:
    report = run_real_sample_eval(
        args.manifest,
        project_root=args.project_root or None,
        provider=MockProvider(),
    )
    report_paths = write_real_sample_report(report, args.reports_dir)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"样本评测：{report['passed']}/{report['total']} 通过，"
            f"通过率 {report['accuracy']:.2%}"
        )
        print(
            "证据分层："
            + "，".join(
                (
                    f"{evidence_type}="
                    f"{summary['passed']}/{summary['total']}"
                )
                for evidence_type, summary in report["by_evidence"].items()
            )
        )
        print(
            "失败统计："
            f"解析 {report['parse_failures']}，"
            f"路由 {report['route_failures']}，"
            f"必需项 {report['required_term_failures']}，"
            f"禁止词 {report['forbidden_term_hits']}，"
            f"运行错误 {report['run_errors']}"
        )
        print("报告文件：")
        for path in report_paths:
            print(f"- {path}")
    return 0 if report["passed"] == report["total"] else 1


def _build_provider(args: argparse.Namespace):
    if args.provider == "mock":
        return MockProvider()
    settings = Settings.from_env()
    return OpenAIResponsesProvider(
        model=args.model,
        api_key=settings.openai_api_key,
    )


def _read_goal(goal: str, goal_file: str) -> str:
    if goal_file:
        return Path(goal_file).read_text(encoding="utf-8")
    return goal


def _module_available(name: str) -> bool:
    try:
        __import__(name)
    except ImportError:
        return False
    return True
