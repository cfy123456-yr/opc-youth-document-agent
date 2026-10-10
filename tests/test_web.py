import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from opc_agent.web import WebApp, create_server, parse_multipart


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(__file__).resolve().parents[1]
        self.app = WebApp(
            output_dir=Path(self.temp_dir.name) / "outputs",
            static_dir=root / "opc_agent" / "web_static",
            examples_dir=root / "examples",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_run_payload_accepts_pasted_text(self):
        payload = self.app.run_payload(
            {
                "task": "contract",
                "content": (
                    "实习协议\n"
                    "乙方提前离职需要支付高额违约金。\n"
                    "公司有权随时终止协议。"
                ),
                "goal": "",
            },
            {},
        )

        self.assertEqual(payload["result"]["task"], "contract")
        self.assertTrue(
            payload["result"]["data"]["requires_human_review"]
        )
        self.assertEqual(
            {item["name"] for item in payload["outputs"]},
            {"report.md", "result.json"},
        )
        self.assertTrue(payload["report_url"].startswith("/api/download?"))

    def test_parse_multipart_file_upload(self):
        boundary = "----opc-test-boundary"
        body = (
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="task"\r\n\r\n'
                "receipt\r\n"
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="file"; '
                'filename="receipts.txt"\r\n'
                "Content-Type: text/plain; charset=utf-8\r\n\r\n"
                "酒店\n2026-09-01 住宿费 320.00元\r\n"
                f"--{boundary}--\r\n"
            ).encode("utf-8")
        )
        fields, files = parse_multipart(
            body,
            f"multipart/form-data; boundary={boundary}",
        )

        self.assertEqual(fields["task"], "receipt")
        self.assertEqual(files["file"]["filename"], "receipts.txt")
        payload = self.app.run_payload(fields, files)
        self.assertEqual(payload["result"]["data"]["total"], 320.0)
        self.assertEqual(len(payload["outputs"]), 3)

    def test_download_path_traversal_is_rejected(self):
        with self.assertRaises(ValueError):
            self.app.resolve_download("../secret.txt")

    def test_download_token_rejects_tampering(self):
        payload = self.app.run_payload(
            {
                "task": "letter",
                "content": "尊敬的老师：我想申请助学金，我会认真学习。",
                "goal": "",
            },
            {},
        )
        token = urllib.parse.parse_qs(
            urllib.parse.urlsplit(payload["report_url"]).query
        )["token"][0]
        encoded, signature = token.split(".", 1)
        replacement = "A" if signature[0] != "A" else "B"
        tampered = f"{encoded}.{replacement}{signature[1:]}"
        with self.assertRaises(ValueError):
            self.app.resolve_download(tampered)

    def test_public_demo_defaults_and_provider_guard(self):
        public_app = WebApp(
            output_dir=Path(self.temp_dir.name) / "public-outputs",
            static_dir=Path(__file__).resolve().parents[1]
            / "opc_agent"
            / "web_static",
            examples_dir=Path(__file__).resolve().parents[1] / "examples",
            public_demo=True,
        )
        self.assertEqual(public_app.retention_seconds, 3600)
        self.assertEqual(public_app.max_runs_per_window, 12)
        with self.assertRaisesRegex(ValueError, "OPC_PUBLIC_ALLOW_MODEL"):
            WebApp(
                output_dir=Path(self.temp_dir.name) / "bad-outputs",
                static_dir=public_app.static_dir,
                examples_dir=public_app.examples_dir,
                provider_name="deepseek",
                public_demo=True,
            )
        with self.assertRaisesRegex(ValueError, "API Key"):
            WebApp(
                output_dir=Path(self.temp_dir.name) / "missing-key-outputs",
                static_dir=public_app.static_dir,
                examples_dir=public_app.examples_dir,
                provider_name="deepseek",
                public_demo=True,
                public_allow_model=True,
            )

    def test_public_online_model_defaults_are_restricted(self):
        app = WebApp(
            output_dir=Path(self.temp_dir.name) / "online-outputs",
            static_dir=Path(__file__).resolve().parents[1]
            / "opc_agent"
            / "web_static",
            examples_dir=Path(__file__).resolve().parents[1] / "examples",
            provider_name="deepseek",
            model="deepseek-chat",
            api_key="test-key",
            public_demo=True,
            public_allow_model=True,
        )

        self.assertEqual(app.max_runs_per_day, 6)
        self.assertEqual(app.global_runs_per_day, 30)
        self.assertEqual(app.max_input_chars, 20000)
        self.assertEqual(app.max_output_tokens, 1600)
        health = app.health_payload()
        self.assertTrue(health["online_model"])
        self.assertEqual(health["provider"], "online")
        self.assertEqual(health["model"], "")

        with self.assertRaisesRegex(ValueError, "确认隐私安全提示"):
            app.run_payload(
                {
                    "task": "letter",
                    "content": "尊敬的老师：我想申请助学金。",
                },
                {},
            )

    def test_input_length_limit_is_enforced(self):
        app = WebApp(
            output_dir=Path(self.temp_dir.name) / "limited-outputs",
            static_dir=self.app.static_dir,
            examples_dir=self.app.examples_dir,
            max_input_chars=5,
        )

        with self.assertRaisesRegex(ValueError, "当前上限为 5 字符"):
            app.run_payload(
                {"task": "letter", "content": "123456"},
                {},
            )

    def test_web_can_build_openai_compatible_agent(self):
        app = WebApp(
            output_dir=Path(self.temp_dir.name) / "model-outputs",
            static_dir=self.app.static_dir,
            examples_dir=self.app.examples_dir,
            provider_name="openai-compatible",
            model="model-name",
            base_url="https://example.test/v1",
            api_key="secret",
        )

        self.assertEqual(
            app.build_agent().provider.name,
            "openai-compatible",
        )

    def test_cleanup_expired_outputs(self):
        run_dir = self.app.output_dir / "old-run"
        run_dir.mkdir(parents=True)
        (run_dir / "report.md").write_text("old", encoding="utf-8")
        old_time = time.time() - 7200
        os.utime(run_dir / "report.md", (old_time, old_time))
        os.utime(run_dir, (old_time, old_time))
        app = WebApp(
            output_dir=self.app.output_dir,
            static_dir=self.app.static_dir,
            examples_dir=self.app.examples_dir,
            retention_seconds=60,
        )
        self.assertEqual(app.cleanup_expired_outputs(force=True), 1)
        self.assertFalse(run_dir.exists())

    def test_empty_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "请粘贴内容"):
            self.app.run_payload({"task": "auto"}, {})


class WebServerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.server = create_server(
            host="127.0.0.1",
            port=0,
            output_dir=Path(self.temp_dir.name) / "outputs",
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        host, port = self.server.server_address[:2]
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp_dir.cleanup()

    def request(
        self,
        path,
        *,
        data=None,
        headers=None,
    ):
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers or {},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, dict(response.headers), response.read()

    def test_static_health_and_examples(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn("青年文书智能助手".encode("utf-8"), body)

        status, _, body = self.request("/api/health")
        self.assertEqual(status, 200)
        health = json.loads(body)
        self.assertTrue(health["ok"])
        self.assertFalse(health["public_demo"])
        self.assertEqual(health["retention_seconds"], 0)

        status, _, body = self.request("/api/examples?task=resume")
        self.assertEqual(status, 200)
        example = json.loads(body)
        self.assertEqual(example["task"], "resume")
        self.assertTrue(example["content"])
        self.assertTrue(example["goal"])

    def test_public_copy_keeps_privacy_notice_provider_neutral(self):
        status, _, page = self.request("/")
        self.assertEqual(status, 200)
        status, _, script = self.request("/app.js")
        self.assertEqual(status, 200)

        public_copy = page.decode("utf-8") + script.decode("utf-8")
        self.assertNotIn("第三方 AI", public_copy)
        self.assertNotIn("AI API", public_copy)
        self.assertNotIn("第三方", public_copy)
        self.assertIn("提交前隐私安全提示", public_copy)
        self.assertIn("请勿提交敏感信息", public_copy)

    def test_run_and_download(self):
        boundary = "----opc-http-boundary"
        body = (
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="task"\r\n\r\n'
                "letter\r\n"
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="content"\r\n\r\n'
                "尊敬的老师：我想申请助学金，我会认真学习。谢谢老师。\r\n"
                f"--{boundary}--\r\n"
            ).encode("utf-8")
        )
        status, _, response_body = self.request(
            "/api/run",
            data=body,
            headers={
                "Content-Type": (
                    f"multipart/form-data; boundary={boundary}"
                )
            },
        )
        self.assertEqual(status, 200)
        payload = json.loads(response_body)
        self.assertEqual(payload["result"]["task"], "letter")

        download_url = urllib.parse.urlsplit(
            payload["report_url"]
        ).path + "?" + urllib.parse.urlsplit(payload["report_url"]).query
        status, headers, report = self.request(download_url)
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn("# 青年文书智能助手".encode("utf-8"), report)

    def test_download_traversal_returns_bad_request(self):
        with self.assertRaises(urllib.error.HTTPError) as context:
            self.request(
                "/api/download?token="
                + urllib.parse.quote("../secret.txt")
            )
        self.assertEqual(context.exception.code, 400)

    def test_run_rate_limit_returns_429(self):
        extra_dir = tempfile.TemporaryDirectory()
        self.addCleanup(extra_dir.cleanup)
        server = create_server(
            host="127.0.0.1",
            port=0,
            output_dir=Path(extra_dir.name) / "outputs",
            max_runs_per_window=1,
            max_concurrent_runs=1,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        host, port = server.server_address[:2]
        base_url = f"http://{host}:{port}"

        boundary = "----opc-rate-limit"
        body = (
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="task"\r\n\r\n'
                "letter\r\n"
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="content"\r\n\r\n'
                "尊敬的老师：我想申请助学金，我会认真学习。\r\n"
                f"--{boundary}--\r\n"
            ).encode("utf-8")
        )
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        }
        request = urllib.request.Request(
            f"{base_url}/api/run",
            data=body,
            headers=headers,
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            self.assertEqual(response.status, 200)
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(context.exception.code, 429)


if __name__ == "__main__":
    unittest.main()
