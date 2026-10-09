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
            url_prefix="/youth",
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
    ):
        parsed = urllib.parse.urlsplit(path)
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": parsed.path,
            "QUERY_STRING": parsed.query,
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": str(len(body)) if body else "",
            "REMOTE_ADDR": "127.0.0.1",
            "wsgi.input": io.BytesIO(body),
        }
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)

        response_body = b"".join(self.application(environ, start_response))
        return captured["status"], captured["headers"], response_body

    def test_health_and_index_are_available_under_prefix(self):
        status, headers, body = self.request("/youth/")
        self.assertTrue(status.startswith("200"))
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn("青年文书智能助手".encode("utf-8"), body)
        self.assertIn(b'href="styles.css"', body)

        status, _, body = self.request("/youth/api/health")
        self.assertTrue(status.startswith("200"))
        health = json.loads(body)
        self.assertTrue(health["ok"])
        self.assertTrue(health["public_demo"])
        self.assertEqual(health["provider"], "mock")

    def test_examples_run_and_download(self):
        status, _, body = self.request("/youth/api/examples?task=letter")
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
            "/youth/api/run",
            method="POST",
            body=request_body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        self.assertTrue(status.startswith("200"))
        payload = json.loads(body)
        self.assertEqual(payload["result"]["task"], "letter")
        self.assertTrue(payload["report_url"].startswith("/youth/api/download?"))

        status, headers, report = self.request(payload["report_url"])
        self.assertTrue(status.startswith("200"))
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn("# 青年文书智能助手".encode("utf-8"), report)

    def test_paths_outside_prefix_are_not_served(self):
        status, _, _ = self.request("/api/health")
        self.assertTrue(status.startswith("404"))


if __name__ == "__main__":
    unittest.main()
