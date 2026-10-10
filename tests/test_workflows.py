import tempfile
import unittest
from pathlib import Path

from opc_agent.agent import YouthDocumentAgent
from opc_agent.models import AgentRequest, TaskType
from opc_agent.providers.base import ModelProvider, ProviderError
from opc_agent.workflows.base import PROVIDER_MAINTENANCE_MESSAGE


class FailingProvider(ModelProvider):
    name = "failing"

    @property
    def available(self) -> bool:
        return True

    def complete(self, system_prompt: str, user_prompt: str) -> str | None:
        raise ProviderError("HTTP 402 Insufficient Balance")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.agent = YouthDocumentAgent(output_dir=Path(self.temp_dir.name))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resume_analysis(self):
        run = self.agent.run(
            AgentRequest(
                task=TaskType.RESUME,
                content=(
                    "张三\nzhang@example.com\n"
                    "负责后端开发，参与项目交付。\n"
                    "使用 Python 和 MySQL 完成接口开发。"
                ),
                goal="Python 后端开发，熟悉 MySQL 和 API",
            )
        )
        self.assertEqual(run.result.task, TaskType.RESUME)
        self.assertIn("match_score", run.result.data)
        quantified = [
            finding
            for finding in run.result.findings
            if "量化" in finding.title
        ]
        self.assertEqual(len(quantified), 1)
        self.assertIn("；", quantified[0].evidence)

    def test_resume_short_action_clause_is_checked(self):
        run = self.agent.run(
            AgentRequest(
                task=TaskType.RESUME,
                content="简历中写：负责接口开发。",
                goal="Python 后端开发",
            )
        )
        quantified = [
            finding
            for finding in run.result.findings
            if finding.title == "缺少量化结果"
        ]
        self.assertEqual(len(quantified), 1)
        self.assertIn("负责接口开发", quantified[0].evidence)

    def test_letter_polish(self):
        run = self.agent.run(
            AgentRequest(
                task=TaskType.LETTER,
                content=(
                    "尊敬的老师：\n"
                    "我觉得我想申请助学金，然后我会认真学习。\n"
                    "谢谢老师。\n申请人：张三"
                ),
                context={"purpose": "申请助学金"},
            )
        )
        self.assertNotIn("我觉得", run.result.data["polished_text"])
        self.assertIn("我认为", run.result.data["polished_text"])

    def test_contract_risk(self):
        run = self.agent.run(
            AgentRequest(
                task=TaskType.CONTRACT,
                content=(
                    "租房合同\n"
                    "第一条 乙方提前退租，押金不退。\n"
                    "第二条 合同期满自动续约。\n"
                    "第三条 甲方概不负责房屋内物品损失。"
                ),
            )
        )
        self.assertEqual(run.result.data["risk_level"], "high")
        self.assertTrue(run.result.data["requires_human_review"])
        self.assertIn("不构成法律意见", run.result.data["disclaimer"])

    def test_receipt_duplicate(self):
        run = self.agent.run(
            AgentRequest(
                task=TaskType.RECEIPT,
                content=(
                    "某某酒店\n2026-09-01 住宿费 320.00元\n"
                    "某某酒店\n2026-09-01 住宿费 320.00元\n"
                    "地铁公司\n2026-09-02 交通费 6.00元"
                ),
            )
        )
        self.assertEqual(run.result.data["total"], 646.0)
        self.assertEqual(len(run.result.data["duplicate_candidates"]), 1)
        self.assertTrue(
            any("重复" in finding.title for finding in run.result.findings)
        )

    def test_provider_failure_shows_maintenance_without_internal_detail(self):
        agent = YouthDocumentAgent(
            provider=FailingProvider(),
            output_dir=Path(self.temp_dir.name) / "failing-provider",
        )
        run = agent.run(
            AgentRequest(
                task=TaskType.LETTER,
                content="尊敬的老师：我想申请助学金，我会认真学习。谢谢老师。",
            )
        )

        self.assertEqual(
            run.result.warnings,
            [PROVIDER_MAINTENANCE_MESSAGE],
        )
        self.assertNotIn("402", run.result.warnings[0])
        self.assertNotIn("Insufficient Balance", run.result.warnings[0])


if __name__ == "__main__":
    unittest.main()
