import io
import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from opc_agent.wsgi import create_application


class WSGIApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(__file__).resolve().parents[1]
        self.application = create_application(
            root,
            output_dir=Path(self.temp_dir.name) / "outputs",
            public_demo=True,
            retention_seconds=3600,
            max_runs_per_window=12,
            max_concurrent_runs=2,
            url_prefix="/agent",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def request(
        self,
        path,
        *,
        method="GET",
        body=b"",
        content_type="",
        remote_addr="127.0.0.1",
        forwarded_for="",
    ):
        parsed = urllib.parse.urlsplit(path)
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": parsed.path,
            "QUERY_STRING": parsed.query,
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": str(len(body)) if body else "",
            "REMOTE_ADDR": remote_addr,
            "wsgi.input": io.BytesIO(body),
        }
        if forwarded_for:
            environ["HTTP_X_FORWARDED_FOR"] = forwarded_for
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)

        response_body = b"".join(self.application(environ, start_response))
        return captured["status"], captured["headers"], response_body

    def test_health_and_index_are_available_under_prefix(self):
        status, headers, body = self.request("/agent/")
        self.assertTrue(status.startswith("200"))
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn("青年文书智能助手".encode("utf-8"), body)
        self.assertIn(b'href="styles.css"', body)

        status, _, body = self.request("/agent/api/health")
        self.assertTrue(status.startswith("200"))
        health = json.loads(body)
        self.assertTrue(health["ok"])
        self.assertTrue(health["public_demo"])
        self.assertEqual(health["provider"], "mock")
        self.assertFalse(health["online_model"])
        self.assertIn("max_input_chars", health)
        self.assertIn("max_runs_per_day", health)

    def test_examples_run_and_download(self):
        status, _, body = self.request("/agent/api/examples?task=letter")
        self.assertTrue(status.startswith("200"))
        example = json.loads(body)
        self.assertEqual(example["task"], "letter")

        boundary = "----opc-wsgi-boundary"
        request_body = (
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
        status, _, body = self.request(
            "/agent/api/run",
            method="POST",
            body=request_body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        self.assertTrue(status.startswith("200"))
        payload = json.loads(body)
        self.assertEqual(payload["result"]["task"], "letter")
        self.assertTrue(payload["report_url"].startswith("/agent/api/download?"))

        status, headers, report = self.request(payload["report_url"])
        self.assertTrue(status.startswith("200"))
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn("# 青年文书智能助手".encode("utf-8"), report)

    def test_paths_outside_prefix_are_not_served(self):
        status, _, _ = self.request("/api/health")
        self.assertTrue(status.startswith("404"))

    def test_forwarded_header_cannot_bypass_ip_limit(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            application = create_application(
                root,
                output_dir=Path(temp_dir) / "outputs",
                public_demo=True,
                max_runs_per_window=1,
                max_concurrent_runs=1,
                url_prefix="/agent",
            )
            boundary = "----opc-forwarded-header"
            request_body = (
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
            captured = {}

            def send(forwarded_for):
                environ = {
                    "REQUEST_METHOD": "POST",
                    "PATH_INFO": "/agent/api/run",
                    "QUERY_STRING": "",
                    "CONTENT_TYPE": (
                        f"multipart/form-data; boundary={boundary}"
                    ),
                    "CONTENT_LENGTH": str(len(request_body)),
                    "REMOTE_ADDR": "203.0.113.20",
                    "HTTP_X_FORWARDED_FOR": forwarded_for,
                    "wsgi.input": io.BytesIO(request_body),
                }

                def start_response(status, headers):
                    captured["status"] = status
                    captured["headers"] = dict(headers)

                return b"".join(application(environ, start_response))

            send("198.51.100.1")
            self.assertTrue(captured["status"].startswith("200"))
            body = send("198.51.100.2")
            self.assertTrue(captured["status"].startswith("429"))
            self.assertEqual(captured["headers"]["Retry-After"], "60")
            self.assertIn("公开演示请求过于频繁".encode("utf-8"), body)


if __name__ == "__main__":
    unittest.main()
