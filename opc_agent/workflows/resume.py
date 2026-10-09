from __future__ import annotations

import re

from opc_agent.models import AgentRequest, Finding, TaskType, WorkflowResult
from opc_agent.providers.base import ModelProvider
from opc_agent.workflows.base import Workflow


STOPWORDS = {
    "负责",
    "参与",
    "完成",
    "进行",
    "相关",
    "工作",
    "项目",
    "经验",
    "能力",
    "要求",
    "岗位",
    "我们",
    "优先",
    "以及",
    "能够",
    "具有",
    "熟悉",
    "掌握",
    "良好的",
}
EXPERIENCE_ACTION_PATTERN = re.compile(
    r"(负责|参与|协助|帮助|完成|使用|实现|开发|设计|优化|维护|推动|支持|搭建)"
)
WEAK_ACTION_PATTERN = re.compile(r"^(负责|参与|协助|帮助)")


def extract_keywords(text: str, limit: int = 30) -> list[str]:
    english = re.findall(r"[A-Za-z][A-Za-z0-9+#._-]{1,}", text.lower())
    chinese_blocks = re.findall(r"[\u4e00-\u9fff]{2,12}", text)
    chinese: list[str] = []
    for block in chinese_blocks:
        if 2 <= len(block) <= 4:
            chinese.append(block)
            continue
        for index in range(len(block) - 1):
            token = block[index : index + 2]
            if token not in STOPWORDS:
                chinese.append(token)

    ordered: list[str] = []
    for token in english + chinese:
        token = token.strip().lower()
        if token in STOPWORDS or token.isdigit() or len(token) < 2:
            continue
        if token not in ordered:
            ordered.append(token)
        if len(ordered) >= limit:
            break
    return ordered


class ResumeWorkflow(Workflow):
    task = TaskType.RESUME

    def run(
        self,
        request: AgentRequest,
        provider: ModelProvider,
    ) -> WorkflowResult:
        baseline = self._local_analysis(request.content, request.goal)
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

    def _local_analysis(self, resume: str, goal: str) -> dict:
        lines: list[str] = []
        for raw_line in resume.splitlines():
            for clause in re.split(r"[。；;]", raw_line):
                clause = clause.strip(" \t-•")
                if not clause:
                    continue
                action = EXPERIENCE_ACTION_PATTERN.search(clause)
                if action:
                    clause = clause[action.start() :].strip()
                lines.append(clause)
        bullets = [
            line
            for line in lines
            if len(line) >= 12
            or (
                len(line) >= 4
                and EXPERIENCE_ACTION_PATTERN.search(line) is not None
            )
        ]
        goal_keywords = extract_keywords(goal, limit=20)
        resume_lower = resume.lower()
        matched = [keyword for keyword in goal_keywords if keyword in resume_lower]
        missing = [keyword for keyword in goal_keywords if keyword not in resume_lower]
        coverage = len(matched) / max(len(goal_keywords), 1)

        finding_groups: dict[str, dict[str, object]] = {}
        rewrite_candidates: list[dict[str, str]] = []

        def add_finding(
            title: str,
            severity: str,
            detail: str,
            evidence: str,
            suggestion: str,
        ) -> None:
            group = finding_groups.setdefault(
                title,
                {
                    "title": title,
                    "severity": severity,
                    "detail": detail,
                    "evidence": [],
                    "suggestion": suggestion,
                },
            )
            evidence_items = group["evidence"]
            if isinstance(evidence_items, list) and evidence not in evidence_items:
                evidence_items.append(evidence)

        experience_bullets = [
            line
            for line in bullets
            if EXPERIENCE_ACTION_PATTERN.search(line)
        ]

        for line in bullets:
            if WEAK_ACTION_PATTERN.search(line):
                add_finding(
                    title="动作词偏弱",
                    severity="medium",
                    detail="部分经历描述更像职责，没有突出个人行动和结果。",
                    evidence=line,
                    suggestion="改成“动作 + 方法 + 结果”，并补充可验证数据。",
                )
                rewrite_candidates.append(
                    {
                        "before": line,
                        "after": f"待补全数据：{line}；说明采取的方法、规模和结果。",
                        "reason": "避免只写职责，增加贡献和量化结果。",
                    }
                )
            if line in experience_bullets and not re.search(r"\d", line):
                add_finding(
                    title="缺少量化结果",
                    severity="medium",
                    detail="部分经历无法判断工作量、速度、规模或业务结果。",
                    evidence=line,
                    suggestion="补充数量、比例、时长、金额或效率变化。",
                )
            if len(line) > 90:
                add_finding(
                    title="单条描述过长",
                    severity="low",
                    detail="部分描述过长，招聘人员难以快速抓住重点。",
                    evidence=line[:90] + "...",
                    suggestion="拆成一条职责信息和一条结果信息。",
                )

        findings = []
        for group in finding_groups.values():
            evidence_items = group["evidence"]
            evidence = "；".join(evidence_items[:3])
            if len(evidence_items) > 3:
                evidence += f"；等 {len(evidence_items)} 条"
            findings.append(
                Finding(
                    title=str(group["title"]),
                    severity=str(group["severity"]),
                    detail=str(group["detail"]),
                    evidence=evidence,
                    suggestion=str(group["suggestion"]),
                )
            )

        if not re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", resume):
            findings.append(
                Finding(
                    title="缺少邮箱",
                    severity="low",
                    detail="简历中没有识别到常用联系方式。",
                    suggestion="添加一个专业邮箱，并检查电话和所在城市。",
                )
            )
        if goal and not matched:
            findings.append(
                Finding(
                    title="岗位关键词覆盖不足",
                    severity="high",
                    detail="简历文本没有覆盖目标岗位的主要关键词。",
                    suggestion="只补充真实具备的技能和经历，不要为了匹配而编造。",
                )
            )

        score = int(round(coverage * 100))
        if not goal:
            score = 0
        risk_level = "high" if score < 35 else "medium" if score < 65 else "low"
        summary = (
            "已完成简历基础审计。"
            if not goal
            else f"已完成岗位匹配审计，关键词覆盖率约为 {score}%。"
        )
        data = {
            "target_role": goal.strip()[:200],
            "match_score": score,
            "match_level": risk_level,
            "matched_keywords": matched[:20],
            "missing_keywords": missing[:20],
            "rewrite_candidates": rewrite_candidates[:20],
            "fact_policy": "禁止补充用户未提供的经历、数字、证书和成果。",
            "need_user_confirmation": [
                candidate["before"] for candidate in rewrite_candidates[:10]
            ],
        }
        confidence = 0.62 if goal else 0.48
        return {
            "summary": summary,
            "data": data,
            "findings": findings,
            "confidence": confidence,
        }

    def _system_prompt(self) -> str:
        return (
            "你是中国青年求职简历顾问。只基于用户提供的真实经历优化，"
            "不得编造学历、项目、数据、证书或职责。输出必须包含："
            "summary、data、findings。findings 为数组，每项包含 "
            "title、severity、detail、evidence、suggestion。"
        )

    def _user_prompt(self, request: AgentRequest) -> str:
        return (
            f"目标岗位：\n{request.goal or '未提供'}\n\n"
            f"简历原文：\n{request.content[:20000]}"
        )
