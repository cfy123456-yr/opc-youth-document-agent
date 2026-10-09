import unittest

from opc_agent.models import TaskType
from opc_agent.router import route_task


class RouterTests(unittest.TestCase):
    def test_resume_route(self):
        decision = route_task("请根据目标岗位 JD 优化我的求职简历")
        self.assertEqual(decision.task, TaskType.RESUME)

    def test_letter_route(self):
        decision = route_task("帮我润色一份助学金申请书，格式要正式")
        self.assertEqual(decision.task, TaskType.LETTER)

    def test_internship_application_letter_beats_job_keyword(self):
        decision = route_task(
            "实习申请信\n\n我申请贵单位的软件测试实习岗位。"
        )
        self.assertEqual(decision.task, TaskType.LETTER)

    def test_funding_request_beats_receipt_mentions(self):
        decision = route_task(
            "学生活动经费申请书\n\n具体金额以实际票据和审批结果为准。"
        )
        self.assertEqual(decision.task, TaskType.LETTER)

    def test_contract_route(self):
        decision = route_task("审查租房合同，重点看押金和违约金条款")
        self.assertEqual(decision.task, TaskType.CONTRACT)

    def test_receipt_route(self):
        decision = route_task("整理发票和小票，生成报销 Excel")
        self.assertEqual(decision.task, TaskType.RECEIPT)

    def test_transport_receipt_route(self):
        decision = route_task("高铁票\n2026-09-10 交通费 553.00元")
        self.assertEqual(decision.task, TaskType.RECEIPT)

    def test_unknown_route(self):
        decision = route_task("今天天气不错")
        self.assertEqual(decision.task, TaskType.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
