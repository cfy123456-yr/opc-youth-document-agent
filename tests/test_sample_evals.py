import json
import tempfile
import unittest
from pathlib import Path

from opc_agent.sample_evals import (
    default_sample_manifest,
    run_real_sample_eval,
    validate_sample_manifest,
    write_real_sample_report,
)


class SampleEvalTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "samples" / "private" / "baselines").mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_manifest(self, rows: list[str]) -> Path:
        manifest = self.root / "samples" / "manifest.csv"
        manifest.write_text(
            "\n".join(
                [
                    (
                        "sample_id,task,path,expected_task,goal_path,"
                        "baseline_path,evidence_type,consent_confirmed,notes"
                    ),
                    *rows,
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return manifest

    def write_baseline(
        self,
        filename: str,
        *,
        required_terms: list[str] | None = None,
        forbidden_terms: list[str] | None = None,
        expected_finding_titles: list[str] | None = None,
        min_findings: int = 0,
    ) -> Path:
        path = (
            self.root
            / "samples"
            / "private"
            / "baselines"
            / filename
        )
        path.write_text(
            json.dumps(
                {
                    "required_terms": required_terms or [],
                    "forbidden_terms": forbidden_terms or [],
                    "expected_finding_titles": expected_finding_titles or [],
                    "min_findings": min_findings,
                    "human_notes": "测试基线",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def test_validate_manifest_reports_progress(self):
        sample = self.root / "samples" / "private" / "letter-001.txt"
        sample.write_text("尊敬的老师：申请助学金。谢谢老师。", encoding="utf-8")
        self.write_baseline("letter-001.json")
        manifest = self.write_manifest(
            [
                (
                    "letter-001,letter,samples/private/letter-001.txt,"
                    "letter,,samples/private/baselines/letter-001.json,"
                    "real,yes,测试申请函"
                )
            ]
        )

        report = validate_sample_manifest(manifest, project_root=self.root)

        self.assertTrue(report["schema_ok"])
        self.assertFalse(report["ready"])
        self.assertEqual(report["task_counts"]["letter"], 1)
        self.assertEqual(report["missing_by_task"]["letter"], 4)

    def test_default_manifest_prefers_ignored_local_file(self):
        template = self.root / "samples" / "manifest.csv"
        template.write_text(
            "sample_id,task,path,expected_task,goal_path,"
            "baseline_path,evidence_type,consent_confirmed,notes\n",
            encoding="utf-8",
        )

        self.assertEqual(default_sample_manifest(self.root), template)

        local = self.root / "samples" / "manifest.local.csv"
        local.write_text(
            "sample_id,task,path,expected_task,goal_path,"
            "baseline_path,evidence_type,consent_confirmed,notes\n",
            encoding="utf-8",
        )

        self.assertEqual(default_sample_manifest(self.root), local)

    def test_validate_manifest_rejects_unsafe_path_and_missing_consent(self):
        manifest = self.write_manifest(
            [
                (
                    "bad-001,letter,../secret.txt,letter,,"
                    "samples/private/baselines/missing.json,real,no,"
                    "路径和许可都无效"
                )
            ]
        )

        report = validate_sample_manifest(manifest, project_root=self.root)

        self.assertFalse(report["schema_ok"])
        self.assertTrue(
            any("不能指向项目目录之外" in issue for issue in report["issues"])
        )
        self.assertTrue(
            any("consent_confirmed" in issue for issue in report["issues"])
        )

    def test_run_real_sample_eval_checks_required_and_forbidden_terms(self):
        sample = self.root / "samples" / "private" / "resume-001.txt"
        sample.write_text(
            "张三\n负责后端接口开发，参与项目交付。",
            encoding="utf-8",
        )
        self.write_baseline(
            "resume-001.json",
            required_terms=["match_score"],
            forbidden_terms=["虚构公司"],
            expected_finding_titles=["缺少量化结果"],
            min_findings=1,
        )
        manifest = self.write_manifest(
            [
                (
                    "resume-001,resume,samples/private/resume-001.txt,"
                    "resume,,samples/private/baselines/resume-001.json,"
                    "real,yes,测试简历"
                )
            ]
        )

        report = run_real_sample_eval(manifest, project_root=self.root)

        self.assertEqual(report["total"], 1)
        self.assertEqual(report["passed"], 1)
        self.assertEqual(report["route_tests"], 0)
        self.assertEqual(report["forbidden_term_hits"], 0)
        self.assertFalse(report["rows"][0]["route_tested"])
        self.assertTrue(report["rows"][0]["finding_coverage"]["matched"] == 1)
        self.assertEqual(report["evidence_counts"]["real"], 1)
        self.assertFalse(report["ready_for_gate_c"])

        report_paths = write_real_sample_report(report, self.root / "reports")
        self.assertEqual(len(report_paths), 2)
        self.assertTrue(Path(report_paths[0]).is_file())
        self.assertIn("样本评测报告", Path(report_paths[1]).read_text(
            encoding="utf-8"
        ))

    def test_run_real_sample_eval_counts_parse_warnings_as_failures(self):
        sample = self.root / "samples" / "private" / "resume-002.unknown"
        sample.write_text("张三\n求职简历\nPython 项目经历", encoding="utf-8")
        self.write_baseline("resume-002.json")
        manifest = self.write_manifest(
            [
                (
                    "resume-002,resume,samples/private/resume-002.unknown,"
                    "resume,,samples/private/baselines/resume-002.json,"
                    "real,yes,解析提示测试"
                )
            ]
        )

        report = run_real_sample_eval(manifest, project_root=self.root)

        self.assertEqual(report["parse_failures"], 1)
        self.assertFalse(report["rows"][0]["parse_ok"])
        self.assertFalse(report["rows"][0]["passed"])
        self.assertTrue(report["rows"][0]["parse_warnings"])

    def test_run_real_sample_eval_tests_auto_routing(self):
        sample = self.root / "samples" / "private" / "letter-001.txt"
        sample.write_text(
            "租房合同\n第一条 乙方提前退租，押金不退。",
            encoding="utf-8",
        )
        self.write_baseline("letter-001.json")
        manifest = self.write_manifest(
            [
                (
                    "letter-001,auto,samples/private/letter-001.txt,"
                    "letter,,samples/private/baselines/letter-001.json,"
                    "real,yes,自动路由失败测试"
                )
            ]
        )

        report = run_real_sample_eval(manifest, project_root=self.root)

        self.assertEqual(report["route_tests"], 1)
        self.assertEqual(report["route_failures"], 1)
        self.assertTrue(report["rows"][0]["route_tested"])
        self.assertFalse(report["rows"][0]["route_ok"])
        self.assertFalse(report["rows"][0]["passed"])

    def test_validate_manifest_rejects_explicit_task_mismatch(self):
        sample = self.root / "samples" / "private" / "resume-001.txt"
        sample.write_text("张三\n负责后端接口开发。", encoding="utf-8")
        self.write_baseline("resume-001.json")
        manifest = self.write_manifest(
            [
                (
                    "resume-001,resume,samples/private/resume-001.txt,"
                    "letter,,samples/private/baselines/resume-001.json,"
                    "real,yes,任务配置不一致"
                )
            ]
        )

        report = validate_sample_manifest(manifest, project_root=self.root)

        self.assertFalse(report["schema_ok"])
        self.assertTrue(
            any("task 设为 auto" in issue for issue in report["issues"])
        )

    def test_public_passed_sample_does_not_make_gate_c_ready(self):
        sample = self.root / "samples" / "private" / "resume-001.txt"
        sample.write_text(
            "张三\n负责后端接口开发，参与项目交付。",
            encoding="utf-8",
        )
        self.write_baseline(
            "resume-001.json",
            required_terms=["match_score"],
            expected_finding_titles=["缺少量化结果"],
            min_findings=1,
        )
        manifest = self.write_manifest(
            [
                (
                    "public-resume-001,auto,"
                    "samples/private/resume-001.txt,resume,,"
                    "samples/private/baselines/resume-001.json,"
                    "public,yes,公开许可回归样本"
                )
            ]
        )

        report = run_real_sample_eval(manifest, project_root=self.root)

        self.assertEqual(report["passed"], 1)
        self.assertEqual(report["real_total"], 0)
        self.assertEqual(report["by_evidence"]["public"]["passed"], 1)
        self.assertFalse(report["ready_for_gate_c"])

    def test_validate_manifest_rejects_unknown_evidence_type(self):
        sample = self.root / "samples" / "private" / "letter-001.txt"
        sample.write_text("尊敬的老师：申请助学金。谢谢老师。", encoding="utf-8")
        self.write_baseline("letter-001.json")
        manifest = self.write_manifest(
            [
                (
                    "letter-001,auto,samples/private/letter-001.txt,"
                    "letter,,samples/private/baselines/letter-001.json,"
                    "unknown,yes,证据类型错误"
                )
            ]
        )

        report = validate_sample_manifest(manifest, project_root=self.root)

        self.assertFalse(report["schema_ok"])
        self.assertTrue(
            any("evidence_type" in issue for issue in report["issues"])
        )


if __name__ == "__main__":
    unittest.main()
