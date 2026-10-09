from __future__ import annotations

from opc_agent.models import TaskDecision, TaskType


TASK_KEYWORDS: dict[TaskType, tuple[tuple[str, int], ...]] = {
    TaskType.RESUME: (
        ("简历", 3),
        ("resume", 3),
        ("cv", 2),
        ("求职", 2),
        ("岗位", 1),
        ("jd", 1),
        ("target role", 2),
        ("工作经历", 2),
        ("项目经历", 2),
    ),
    TaskType.LETTER: (
        ("申请书", 4),
        ("申请信", 3),
        ("求职信", 4),
        ("辞职信", 4),
        ("请假条", 4),
        ("助学金", 2),
        ("cover letter", 4),
        ("application letter", 4),
        ("润色", 1),
        ("措辞", 1),
        ("格式", 1),
    ),
    TaskType.CONTRACT: (
        ("合同", 4),
        ("协议", 4),
        ("条款", 2),
        ("甲方", 1),
        ("乙方", 1),
        ("违约", 2),
        ("押金", 2),
        ("竞业", 2),
        ("租房", 1),
        ("实习协议", 5),
        ("离职协议", 5),
        ("contract", 4),
        ("lease", 4),
    ),
    TaskType.RECEIPT: (
        ("发票", 3),
        ("小票", 3),
        ("车票", 2),
        ("高铁", 2),
        ("机票", 2),
        ("打车", 2),
        ("出租车", 2),
        ("酒店", 1),
        ("住宿", 1),
        ("餐费", 1),
        ("报销", 2),
        ("票据", 2),
        ("金额", 1),
        ("税额", 1),
        ("invoice", 3),
        ("receipt", 3),
        ("expense", 2),
        ("报销单", 3),
    ),
}


def route_task(text: str, source: str = "") -> TaskDecision:
    haystack = f"{source}\n{text}".lower()
    scores = {task.value: 0 for task in TASK_KEYWORDS}

    for task, keywords in TASK_KEYWORDS.items():
        for keyword, weight in keywords:
            if keyword.lower() in haystack:
                scores[task.value] += weight

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_task, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if best_score == 0:
        return TaskDecision(
            task=TaskType.UNKNOWN,
            confidence=0.0,
            scores=scores,
            reason="没有识别到明确的任务关键词。",
        )

    total = sum(scores.values())
    separation = (best_score - second_score) / max(best_score, 1)
    confidence = min(0.98, 0.45 + 0.35 * (best_score / max(total, 1)) + 0.2 * separation)
    matched = [
        keyword
        for keyword, _ in TASK_KEYWORDS[TaskType(best_task)]
        if keyword.lower() in haystack
    ]

    return TaskDecision(
        task=TaskType(best_task),
        confidence=round(confidence, 2),
        scores=scores,
        reason=f"主要命中：{', '.join(matched[:6])}",
    )
