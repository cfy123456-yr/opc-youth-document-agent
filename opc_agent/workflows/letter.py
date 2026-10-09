from __future__ import annotations

import re

from opc_agent.models import AgentRequest, Finding, TaskType, WorkflowResult
from opc_agent.providers.base import ModelProvider
from opc_agent.workflows.base import Workflow


INFORMAL_REPLACEMENTS = {
    "我觉得": "我认为",
    "特别想": "希望",
    "真的非常": "非常",
    "然后": "随后",
    "还有就是": "此外",
    "挺好的": "表现良好",
}


class LetterWorkflow(Workflow):
    task = TaskType.LETTER

    def run(
        self,
        request: AgentRequest,
        provider: ModelProvider,
    ) -> WorkflowResult:
        baseline = self._local_polish(request.content, request.context)
        model_data, warning = self.model_json(
            provider,
            self._system_prompt(),
            self._user_prompt(request),
        )
        warnings = [warning] if warning else []
        if model_data:
            baseline["data"].update(model_data.get("data", {}))
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
            baseline["summary"] = model_data.get("summary", baseline["summary"])
            baseline["confidence"] = min(0.98, baseline["confidence"] + 0.1)

        return WorkflowResult(
            task=self.task,
            summary=baseline["summary"],
            data=baseline["data"],
            findings=baseline["findings"],
            warnings=warnings,
            confidence=baseline["confidence"],
        )

    def _local_polish(self, content: str, context: dict) -> dict:
        polished = re.sub(r"[ \t]+", " ", content).strip()
        changes: list[dict[str, str]] = []
        for before, after in INFORMAL_REPLACEMENTS.items():
            if before in polished:
                polished = polished.replace(before, after)
                changes.append({"before": before, "after": after})

        findings: list[Finding] = []
        if not re.search(r"(尊敬的|亲爱的|敬爱的|Dear)", content[:160], flags=re.I):
            findings.append(
                Finding(
                    title="缺少称呼",
                    severity="low",
                    detail="正文开头没有识别到明确称呼。",
                    suggestion="根据收件人身份添加“尊敬的老师”“尊敬的招聘负责人”等称呼。",
                )
            )
        if not re.search(r"(此致|敬礼|谢谢|感谢|申请人|此致|Sincerely|Regards)", content[-240:]):
            findings.append(
                Finding(
                    title="结尾不完整",
                    severity="medium",
                    detail="没有识别到常见结尾、感谢或署名区域。",
                    suggestion="补充结尾礼貌用语、姓名和日期。",
                )
            )
        long_sentences = [
            sentence
            for sentence in re.split(r"[。！？!?]", content)
            if len(sentence.strip()) > 80
        ]
        if long_sentences:
            findings.append(
                Finding(
                    title="长句较多",
                    severity="low",
                    detail="长句会降低申请材料的可读性。",
                    evidence=long_sentences[0][:100],
                    suggestion="每段只表达一个重点，并拆开超过 80 字的句子。",
                )
            )

        purpose = str(context.get("purpose", "")).strip()
        if purpose and purpose not in content:
            findings.append(
                Finding(
                    title="用途不明确",
                    severity="medium",
                    detail="正文没有清楚说明申请目的。",
                    suggestion=f"在开头明确写出：{purpose}。",
                )
            )

        data = {
            "purpose": purpose,
            "polished_text": polished,
            "changes": changes,
            "fact_policy": "只优化语言和格式，不新增经历、理由、承诺或事实。",
            "manual_checks": [
                "核对姓名、日期、联系方式和收件人称呼。",
                "确认申请理由和事实没有在润色过程中被改变。",
            ],
        }
        return {
            "summary": "已完成申请书函润色和格式检查。",
            "data": data,
            "findings": findings,
            "confidence": 0.66,
        }

    def _system_prompt(self) -> str:
        return (
            "你是中文书面表达编辑。保留事实、身份、时间、金额和承诺，"
            "只润色语言、结构和格式。不得编造经历或理由。输出 JSON，"
            "包含 summary、data 和 findings。data 至少包含 polished_text。"
        )

    def _user_prompt(self, request: AgentRequest) -> str:
        purpose = request.context.get("purpose", "")
        return (
            f"用途：{purpose or '未提供'}\n"
            f"语气要求：{request.options.get('tone', '正式、礼貌、简洁')}\n\n"
            f"初稿：\n{request.content[:20000]}"
        )

