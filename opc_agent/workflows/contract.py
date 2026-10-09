from __future__ import annotations

import re

from opc_agent.models import AgentRequest, Finding, TaskType, WorkflowResult
from opc_agent.providers.base import ModelProvider
from opc_agent.workflows.base import Workflow


RISK_RULES = (
    {
        "pattern": r"(概不退还|不予退还|押金不退|定金不退)",
        "title": "退款或押金风险",
        "severity": "high",
        "detail": "条款可能直接排除退款或押金返还权利。",
        "suggestion": "确认退款条件、返还期限、扣除依据和争议处理方式。",
    },
    {
        "pattern": r"(自动续约|自动延期|期满自动)",
        "title": "自动续约风险",
        "severity": "high",
        "detail": "合同可能在没有明确确认的情况下自动延长。",
        "suggestion": "要求改为到期前书面确认续约，并明确退出方式。",
    },
    {
        "pattern": r"(放弃一切|放弃全部|不再主张|不得主张)",
        "title": "权利放弃风险",
        "severity": "high",
        "detail": "条款可能要求一方放弃较广泛的法律权利。",
        "suggestion": "明确放弃的权利范围，删除概括性放弃条款。",
    },
    {
        "pattern": r"(违约金.*[0-9]{4,}|[0-9]+倍|月租金.*倍|高额违约金)",
        "title": "违约金异常",
        "severity": "high",
        "detail": "违约金或赔偿标准可能明显过高。",
        "suggestion": "要求约定合理、可计算、与实际损失相匹配的违约金。",
    },
    {
        "pattern": r"(竞业限制|竞业禁止)",
        "title": "竞业限制",
        "severity": "high",
        "detail": "条款可能限制离职后的就业范围。",
        "suggestion": "确认限制范围、地域、期限和补偿标准。",
    },
    {
        "pattern": r"(概不负责|不承担任何责任|免除.*责任)",
        "title": "责任免除",
        "severity": "high",
        "detail": "条款可能过度免除一方责任。",
        "suggestion": "要求区分故意、重大过失和一般过失，避免全面免责。",
    },
    {
        "pattern": r"(最终解释权|随时变更|单方变更|无需通知)",
        "title": "单方决定权",
        "severity": "medium",
        "detail": "一方可能可以单方面解释或修改重要规则。",
        "suggestion": "改为双方书面确认，并保留变更前后的通知和退出机制。",
    },
    {
        "pattern": r"(单方解除|有权随时终止|无须理由)",
        "title": "单方解除权",
        "severity": "medium",
        "detail": "解除条件可能不对等或过于宽泛。",
        "suggestion": "明确解除条件、通知期限、结算方式和过渡安排。",
    },
    {
        "pattern": r"(加班.*不给|无加班费|不支付加班|自愿放弃加班费)",
        "title": "劳动补偿风险",
        "severity": "high",
        "detail": "条款可能排除加班工资或法定劳动补偿。",
        "suggestion": "保留法律规定的劳动报酬和补偿表述，进行人工复核。",
    },
    {
        "pattern": r"(培训费|服务期|提前离职.*赔偿)",
        "title": "培训费与服务期",
        "severity": "medium",
        "detail": "提前离职可能触发培训费或服务期责任。",
        "suggestion": "确认培训费用凭证、服务期限和违约金计算方式。",
    },
    {
        "pattern": r"(争议.*管辖|提交.*法院|仲裁)",
        "title": "争议解决条款",
        "severity": "medium",
        "detail": "争议解决地点或机构可能增加维权成本。",
        "suggestion": "确认管辖地和仲裁机构，评估异地维权成本。",
    },
)


class ContractWorkflow(Workflow):
    task = TaskType.CONTRACT

    def run(
        self,
        request: AgentRequest,
        provider: ModelProvider,
    ) -> WorkflowResult:
        baseline = self._local_review(request.content)
        model_data, warning = self.model_json(
            provider,
            self._system_prompt(),
            self._user_prompt(request),
        )
        warnings = [warning] if warning else []
        if model_data:
            for item in model_data.get("findings", []):
                if isinstance(item, dict) and item.get("title"):
                    baseline["findings"].append(
                        Finding(
                            title=str(item.get("title", "")),
                            severity=str(item.get("severity", "medium")),
                            detail=str(item.get("detail", "")),
                            evidence=str(item.get("evidence", "")),
                            suggestion=str(item.get("suggestion", "")),
                        )
                    )
            baseline["data"].update(model_data.get("data", {}))
            baseline["summary"] = model_data.get("summary", baseline["summary"])
            baseline["confidence"] = min(0.95, baseline["confidence"] + 0.1)

        return WorkflowResult(
            task=self.task,
            summary=baseline["summary"],
            data=baseline["data"],
            findings=baseline["findings"],
            warnings=warnings,
            confidence=baseline["confidence"],
        )

    def _local_review(self, content: str) -> dict:
        findings: list[Finding] = []
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        seen: set[tuple[str, str]] = set()

        for rule in RISK_RULES:
            match = re.search(rule["pattern"], content, flags=re.I | re.S)
            if not match:
                continue
            evidence = self._evidence(lines, match.group(0))
            key = (str(rule["title"]), evidence)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                Finding(
                    title=str(rule["title"]),
                    severity=str(rule["severity"]),
                    detail=str(rule["detail"]),
                    evidence=evidence,
                    suggestion=str(rule["suggestion"]),
                )
            )

        high = sum(1 for finding in findings if finding.severity == "high")
        medium = sum(1 for finding in findings if finding.severity == "medium")
        low = sum(1 for finding in findings if finding.severity == "low")
        score = min(100, high * 28 + medium * 12 + low * 4)
        level = "high" if high else "medium" if medium else "low"
        data = {
            "risk_score": score,
            "risk_level": level,
            "risk_counts": {"high": high, "medium": medium, "low": low},
            "requires_human_review": bool(high),
            "disclaimer": (
                "本结果仅用于辅助理解合同文本，不构成法律意见，"
                "不能替代律师或专业机构审查。"
            ),
        }
        summary = (
            f"发现 {len(findings)} 个需关注条款，"
            f"其中高风险 {high} 个。"
        )
        return {
            "summary": summary,
            "data": data,
            "findings": findings,
            "confidence": 0.58,
        }

    @staticmethod
    def _evidence(lines: list[str], matched_text: str) -> str:
        for line in lines:
            if matched_text in line:
                return line[:220]
        return matched_text[:220]

    def _system_prompt(self) -> str:
        return (
            "你是中国青年常见合同的风险识别助手。你只做辅助理解，"
            "不提供正式法律意见，不虚构法条。输出 JSON，包含 summary、"
            "data 和 findings。findings 每项包含 title、severity、detail、"
            "evidence、suggestion。高风险必须建议人工复核。"
        )

    def _user_prompt(self, request: AgentRequest) -> str:
        return (
            f"适用地区：{request.context.get('jurisdiction', '中国大陆')}\n"
            f"合同类型：{request.context.get('contract_type', '未说明')}\n\n"
            f"合同文本：\n{request.content[:30000]}"
        )

