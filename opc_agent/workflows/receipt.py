from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from opc_agent.models import AgentRequest, Finding, TaskType, WorkflowResult
from opc_agent.providers.base import ModelProvider
from opc_agent.workflows.base import Workflow


DATE_PATTERNS = (
    r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?",
)

AMOUNT_PATTERNS = (
    r"[¥￥]\s*(\d+(?:\.\d{1,2})?)",
    r"(\d+(?:\.\d{1,2})?)\s*元",
    r"(?:金额|合计|总计|实付|支付|价税合计)[:：\s]*(\d+(?:\.\d{1,2})?)",
)

CATEGORY_KEYWORDS = {
    "交通": ("打车", "出租车", "地铁", "公交", "火车", "高铁", "机票", "航空", "客运"),
    "餐饮": ("餐饮", "餐费", "饭店", "餐厅", "咖啡", "奶茶", "外卖"),
    "住宿": ("酒店", "宾馆", "住宿", "旅馆"),
    "办公": ("办公", "文具", "打印", "复印", "耗材"),
    "通讯": ("话费", "流量", "宽带", "通信"),
}


class ReceiptWorkflow(Workflow):
    task = TaskType.RECEIPT

    def run(
        self,
        request: AgentRequest,
        provider: ModelProvider,
    ) -> WorkflowResult:
        baseline = self._local_extract(request.content)
        model_data, warning = self.model_json(
            provider,
            self._system_prompt(),
            self._user_prompt(request),
        )
        warnings = [warning] if warning else []
        if model_data and isinstance(model_data.get("data", {}).get("items"), list):
            baseline["data"].update(model_data["data"])
            baseline["summary"] = model_data.get("summary", baseline["summary"])
            baseline["confidence"] = min(0.92, baseline["confidence"] + 0.1)

        return WorkflowResult(
            task=self.task,
            summary=baseline["summary"],
            data=baseline["data"],
            findings=baseline["findings"],
            warnings=warnings,
            confidence=baseline["confidence"],
        )

    def _local_extract(self, content: str) -> dict:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        items: list[dict] = []
        findings: list[Finding] = []

        for index, line in enumerate(lines):
            amount = self._find_amount(line)
            if amount is None:
                continue
            date_value = self._find_date(line)
            if not date_value:
                for nearby in reversed(lines[max(0, index - 3) : index]):
                    date_value = self._find_date(nearby)
                    if date_value:
                        break
            merchant = self._find_merchant(lines, index)
            category = self._categorize(f"{merchant} {line}")
            items.append(
                {
                    "merchant": merchant,
                    "date": date_value,
                    "amount": round(amount, 2),
                    "category": category,
                    "evidence": line[:220],
                    "needs_confirmation": not merchant or not date_value,
                }
            )

        duplicates = self._find_duplicates(items)
        if duplicates:
            findings.append(
                Finding(
                    title="疑似重复票据",
                    severity="medium",
                    detail="存在商家、日期和金额相同的票据，可能重复报销。",
                    evidence="; ".join(item["key"] for item in duplicates[:5]),
                    suggestion="核对票据原件或报销批次，删除重复记录。",
                )
            )
        missing_fields = sum(
            1 for item in items if item["needs_confirmation"]
        )
        if missing_fields:
            findings.append(
                Finding(
                    title="字段需要确认",
                    severity="medium",
                    detail=f"{missing_fields} 条票据未识别到完整日期或商家。",
                    suggestion="在导出前人工核对缺失字段，避免报销错误。",
                )
            )
        if not items:
            findings.append(
                Finding(
                    title="未识别到票据",
                    severity="high",
                    detail="本地规则没有从文本中识别出金额和日期。",
                    suggestion="检查 OCR 文本，或接入 PaddleOCR 后重新识别图片。",
                )
            )

        category_totals: Counter[str] = Counter()
        for item in items:
            category_totals[item["category"]] += item["amount"]
        total = round(sum(item["amount"] for item in items), 2)
        data = {
            "items": items,
            "total": total,
            "category_totals": dict(category_totals),
            "duplicate_candidates": duplicates,
            "currency": "CNY",
        }
        summary = f"识别 {len(items)} 条票据，合计 {total:.2f} 元。"
        return {
            "summary": summary,
            "data": data,
            "findings": findings,
            "confidence": 0.72 if items else 0.3,
        }

    @staticmethod
    def _find_amount(line: str) -> float | None:
        for pattern in AMOUNT_PATTERNS:
            match = re.search(pattern, line)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None

    @staticmethod
    def _find_date(line: str) -> str | None:
        for pattern in DATE_PATTERNS:
            match = re.search(pattern, line)
            if match:
                year, month, day = (int(value) for value in match.groups())
                try:
                    return datetime(year, month, day).date().isoformat()
                except ValueError:
                    return None
        return None

    @staticmethod
    def _find_merchant(lines: list[str], amount_index: int) -> str:
        meta_prefixes = ("金额", "合计", "总计", "实付", "支付", "日期", "发票")
        for candidate in reversed(lines[max(0, amount_index - 3) : amount_index]):
            if candidate.startswith(meta_prefixes):
                continue
            if re.search(r"[¥￥]|\d+\.\d{2}", candidate):
                continue
            if len(candidate) >= 2:
                return candidate[:80]
        return ""

    @staticmethod
    def _categorize(text: str) -> str:
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return category
        return "其他"

    @staticmethod
    def _find_duplicates(items: list[dict]) -> list[dict]:
        seen: set[tuple[str, str, float]] = set()
        duplicates: list[dict] = []
        for item in items:
            key = (
                item["merchant"].strip(),
                item["date"] or "",
                item["amount"],
            )
            if not all(key):
                continue
            if key in seen:
                duplicates.append(
                    {
                        "merchant": key[0],
                        "date": key[1],
                        "amount": key[2],
                        "key": f"{key[0]} / {key[1]} / {key[2]:.2f}",
                    }
                )
            seen.add(key)
        return duplicates

    def _system_prompt(self) -> str:
        return (
            "你是票据整理助手。只提取文本中已有的商家、日期、金额和类别，"
            "禁止猜测。输出 JSON，包含 summary、data、findings。data.items "
            "每项包含 merchant、date、amount、category、evidence、"
            "needs_confirmation。金额计算必须与明细一致。"
        )

    def _user_prompt(self, request: AgentRequest) -> str:
        return (
            f"默认币种：{request.options.get('currency', 'CNY')}\n\n"
            f"票据 OCR 或文本：\n{request.content[:30000]}"
        )
