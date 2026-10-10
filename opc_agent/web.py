from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import mimetypes
import secrets
import shutil
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from collections import deque
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from opc_agent.agent import YouthDocumentAgent
from opc_agent.config import (
    DEFAULT_MAX_CONCURRENT_RUNS,
    DEFAULT_MAX_UPLOAD_BYTES,
    Settings,
)
from opc_agent.console import configure_stdio
from opc_agent.models import AgentRequest, TaskType
from opc_agent.parsers import parse_document
from opc_agent.providers import ProviderError, create_provider
from opc_agent.quota import QuotaDecision, UsageQuota


DEFAULT_PUBLIC_RETENTION_SECONDS = 3600
DEFAULT_PUBLIC_RUNS_PER_WINDOW = 12
DEFAULT_PUBLIC_RUNS_PER_DAY = 6
DEFAULT_PUBLIC_GLOBAL_RUNS_PER_DAY = 30
DEFAULT_PUBLIC_MAX_INPUT_CHARS = 20000
DEFAULT_PUBLIC_MAX_OUTPUT_TOKENS = 1600
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60
SECURITY_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)
EXAMPLE_FILES = {
    TaskType.RESUME: "resume.txt",
    TaskType.LETTER: "letter.txt",
    TaskType.CONTRACT: "contract.txt",
    TaskType.RECEIPT: "receipts.txt",
}


@dataclass(slots=True)
class WebApp:
    output_dir: Path
    static_dir: Path
    examples_dir: Path
    provider_name: str = "mock"
    model: str = ""
    base_url: str = ""
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    public_demo: bool = False
    public_allow_model: bool = False
    retention_seconds: int = 0
    max_runs_per_window: int = 0
    max_runs_per_day: int = 0
    global_runs_per_day: int = 0
    rate_limit_window_seconds: int = DEFAULT_RATE_LIMIT_WINDOW_SECONDS
    max_concurrent_runs: int = DEFAULT_MAX_CONCURRENT_RUNS
    max_input_chars: int = 0
    max_output_tokens: int = 0
    request_timeout_seconds: int = 45
    quota_db_path: Path | None = None
    url_prefix: str = ""
    api_key: str = field(default="", repr=False)
    _download_secret: bytes = field(
        default_factory=lambda: secrets.token_bytes(32),
        init=False,
        repr=False,
    )
    _state_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )
    _run_slots: threading.BoundedSemaphore = field(init=False, repr=False)
    _rate_buckets: dict[str, deque[float]] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _quota: UsageQuota | None = field(default=None, init=False, repr=False)
    _last_cleanup: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_upload_bytes = max(1, int(self.max_upload_bytes))
        self.max_concurrent_runs = max(1, int(self.max_concurrent_runs))
        self.rate_limit_window_seconds = max(
            1,
            int(self.rate_limit_window_seconds),
        )
        self.retention_seconds = max(0, int(self.retention_seconds))
        self.max_runs_per_window = max(0, int(self.max_runs_per_window))
        self.max_runs_per_day = max(0, int(self.max_runs_per_day))
        self.global_runs_per_day = max(0, int(self.global_runs_per_day))
        self.max_input_chars = max(0, int(self.max_input_chars))
        self.max_output_tokens = max(0, int(self.max_output_tokens))
        self.request_timeout_seconds = max(
            5,
            int(self.request_timeout_seconds),
        )
        self.url_prefix = self.url_prefix.strip().rstrip("/")
        if self.url_prefix == "/":
            self.url_prefix = ""
        elif self.url_prefix and not self.url_prefix.startswith("/"):
            self.url_prefix = f"/{self.url_prefix}"
        if self.public_demo:
            if self.provider_name != "mock":
                if not self.public_allow_model:
                    raise ValueError(
                        "公网在线模型未显式启用，请设置 "
                        "OPC_PUBLIC_ALLOW_MODEL=true。"
                    )
                if not self.api_key.strip():
                    raise ValueError("公网在线模型缺少 API Key。")
            if self.retention_seconds == 0:
                self.retention_seconds = DEFAULT_PUBLIC_RETENTION_SECONDS
            if self.max_runs_per_window == 0:
                self.max_runs_per_window = DEFAULT_PUBLIC_RUNS_PER_WINDOW
            if (
                self.provider_name != "mock"
                and self.max_runs_per_day == 0
            ):
                self.max_runs_per_day = DEFAULT_PUBLIC_RUNS_PER_DAY
            if (
                self.provider_name != "mock"
                and self.global_runs_per_day == 0
            ):
                self.global_runs_per_day = DEFAULT_PUBLIC_GLOBAL_RUNS_PER_DAY
            if self.provider_name != "mock" and self.max_input_chars == 0:
                self.max_input_chars = DEFAULT_PUBLIC_MAX_INPUT_CHARS
            if self.provider_name != "mock" and self.max_output_tokens == 0:
                self.max_output_tokens = DEFAULT_PUBLIC_MAX_OUTPUT_TOKENS
        if self.max_runs_per_day > 0 or self.global_runs_per_day > 0:
            self._quota = UsageQuota(
                self.quota_db_path or self.output_dir / "usage.sqlite3",
                per_ip_limit=self.max_runs_per_day,
                global_limit=self.global_runs_per_day,
            )
        self._run_slots = threading.BoundedSemaphore(
            self.max_concurrent_runs
        )

    def build_agent(self) -> YouthDocumentAgent:
        provider = create_provider(
            provider_name=self.provider_name,
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            max_tokens=self.max_output_tokens,
            timeout_seconds=self.request_timeout_seconds,
        )
        return YouthDocumentAgent(
            provider=provider,
            output_dir=self.output_dir,
        )

    def run_payload(
        self,
        fields: dict[str, str],
        files: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        task = TaskType(fields.get("task", TaskType.AUTO.value))
        content = fields.get("content", "").strip()
        goal = fields.get("goal", "").strip()
        source = "web-input"
        warnings: list[str] = []

        upload = files.get("file")
        if upload and upload.get("content"):
            filename = _safe_filename(
                str(upload.get("filename") or "upload.txt")
            )
            if not filename:
                filename = "upload.txt"
            with tempfile.TemporaryDirectory(prefix="opc-web-upload-") as temp_dir:
                upload_path = Path(temp_dir) / filename
                upload_path.write_bytes(upload["content"])
                parsed = parse_document(upload_path)
                content = parsed.text
                source = filename
                warnings = parsed.warnings

        if not content:
            raise ValueError("请粘贴内容或选择一份文件。")
        if (
            self.public_demo
            and self.provider_name != "mock"
            and fields.get("consent") != "accepted"
        ):
            raise ValueError("请先阅读并确认隐私安全提示。")
        if self.max_input_chars > 0 and len(content) > self.max_input_chars:
            raise ValueError(
                f"文书内容过长，当前上限为 {self.max_input_chars} 字符。"
            )

        agent = self.build_agent()
        run = agent.run(
            AgentRequest(
                task=task,
                content=content,
                source=source,
                goal=goal,
            ),
            warnings=warnings,
        )
        payload = run.to_dict()
        payload["outputs"] = [
            {
                "name": Path(path).name,
                "download_url": self.download_url(path),
            }
            for path in run.output_files
        ]
        report_path = next(
            (
                path
                for path in run.output_files
                if Path(path).name == "report.md"
            ),
            None,
        )
        payload["report_url"] = (
            self.download_url(report_path) if report_path else ""
        )
        return payload

    def example_payload(self, task_value: str) -> dict[str, str]:
        try:
            task = TaskType(task_value)
        except ValueError as exc:
            raise ValueError("未知示例类型。") from exc
        if task == TaskType.AUTO:
            task = TaskType.CONTRACT
        filename = EXAMPLE_FILES.get(task)
        if not filename:
            raise ValueError("该任务暂时没有示例。")

        text_path = self.examples_dir / filename
        if not text_path.exists():
            raise FileNotFoundError(f"示例文件不存在：{text_path}")

        goal = ""
        if task == TaskType.RESUME:
            goal_path = self.examples_dir / "job_description.txt"
            if goal_path.exists():
                goal = goal_path.read_text(encoding="utf-8")
        return {
            "task": task.value,
            "content": text_path.read_text(encoding="utf-8"),
            "goal": goal,
        }

    def download_url(self, path: str | Path) -> str:
        relative = Path(path).resolve().relative_to(self.output_dir.resolve())
        token = self._create_download_token(relative)
        prefix = self.url_prefix
        return f"{prefix}/api/download?token={urllib.parse.quote(token)}"

    def resolve_download(self, token: str) -> Path:
        relative_path = self._verify_download_token(token)
        if not relative_path:
            raise ValueError("缺少下载路径。")
        root = self.output_dir.resolve()
        candidate = (root / relative_path).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("下载路径无效。")
        if not candidate.is_file():
            raise FileNotFoundError("下载文件不存在。")
        return candidate

    def allow_run(self, client_ip: str) -> QuotaDecision:
        if self.max_runs_per_window <= 0:
            if self._quota is None:
                return QuotaDecision(True)
            return self._quota.try_consume(client_ip)
        now = time.monotonic()
        window = self.rate_limit_window_seconds
        with self._state_lock:
            bucket = self._rate_buckets.setdefault(client_ip, deque())
            while bucket and now - bucket[0] >= window:
                bucket.popleft()
            if len(bucket) >= self.max_runs_per_window:
                retry_after = max(1, int(window - (now - bucket[0]) + 0.999))
                return QuotaDecision(
                    False,
                    "公开演示请求过于频繁，请稍后再试。",
                    retry_after,
                )
            bucket.append(now)
            if len(self._rate_buckets) > 2048:
                self._drop_stale_rate_buckets(now)
        if self._quota is not None:
            return self._quota.try_consume(client_ip)
        return QuotaDecision(True)

    def health_payload(self) -> dict[str, Any]:
        online_model = self.provider_name != "mock"
        public_provider = (
            "online"
            if self.public_demo and online_model
            else self.provider_name
        )
        return {
            "ok": True,
            "provider": public_provider,
            "model": "" if self.public_demo and online_model else self.model,
            "public_demo": self.public_demo,
            "retention_seconds": self.retention_seconds,
            "max_upload_bytes": self.max_upload_bytes,
            "max_input_chars": self.max_input_chars,
            "max_runs_per_day": self.max_runs_per_day,
            "global_runs_per_day": self.global_runs_per_day,
            "online_model": online_model,
        }

    def acquire_run_slot(self) -> bool:
        return self._run_slots.acquire(blocking=False)

    def release_run_slot(self) -> None:
        self._run_slots.release()

    def cleanup_expired_outputs(self, force: bool = False) -> int:
        if self.retention_seconds <= 0:
            return 0
        now = time.time()
        minimum_interval = min(
            max(self.retention_seconds // 4, 5),
            900,
        )
        with self._state_lock:
            if not force and now - self._last_cleanup < minimum_interval:
                return 0
            self._last_cleanup = now

        removed = 0
        for child in self.output_dir.iterdir():
            if not child.is_dir():
                continue
            try:
                modified = max(
                    child.stat().st_mtime,
                    *(
                        item.stat().st_mtime
                        for item in child.iterdir()
                        if item.is_file()
                    ),
                )
            except (OSError, ValueError):
                continue
            if now - modified <= self.retention_seconds:
                continue
            shutil.rmtree(child, ignore_errors=True)
            if not child.exists():
                removed += 1
        return removed

    def _drop_stale_rate_buckets(self, now: float) -> None:
        stale_before = now - self.rate_limit_window_seconds
        stale_keys = [
            key
            for key, bucket in self._rate_buckets.items()
            if not bucket or bucket[-1] < stale_before
        ]
        for key in stale_keys:
            self._rate_buckets.pop(key, None)

    def _create_download_token(self, relative_path: Path) -> str:
        expires = (
            int(time.time()) + self.retention_seconds
            if self.retention_seconds > 0
            else 0
        )
        payload = json.dumps(
            {"path": relative_path.as_posix(), "expires": expires},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        encoded = _b64url_encode(payload)
        signature = hmac.new(
            self._download_secret,
            encoded,
            hashlib.sha256,
        ).digest()
        return f"{encoded.decode('ascii')}.{_b64url_encode(signature).decode('ascii')}"

    def _verify_download_token(self, token: str) -> str:
        if not token:
            raise ValueError("缺少下载路径。")
        try:
            encoded_text, signature_text = token.split(".", 1)
            encoded = encoded_text.encode("ascii")
            signature = _b64url_decode(signature_text)
        except (UnicodeEncodeError, ValueError) as exc:
            raise ValueError("下载链接无效。") from exc

        expected = hmac.new(
            self._download_secret,
            encoded,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("下载链接无效。")
        try:
            payload = json.loads(_b64url_decode(encoded_text).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError("下载链接无效。") from exc

        expires = int(payload.get("expires", 0))
        if expires and expires < int(time.time()):
            raise ValueError("下载链接已过期，请重新运行。")
        relative_path = str(payload.get("path") or "")
        if not relative_path or Path(relative_path).is_absolute():
            raise ValueError("下载链接无效。")
        return relative_path


class WebRequestHandler(BaseHTTPRequestHandler):
    server_version = "YouthDocWeb/0.2"
    timeout = 30

    @property
    def app(self) -> WebApp:
        return self.server.app  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        try:
            self.app.cleanup_expired_outputs()
            if parsed.path == "/api/health":
                self._send_json(self.app.health_payload())
                return
            if parsed.path == "/api/examples":
                query = urllib.parse.parse_qs(parsed.query)
                task_value = query.get("task", [TaskType.CONTRACT.value])[0]
                self._send_json(self.app.example_payload(task_value))
                return
            if parsed.path == "/api/download":
                query = urllib.parse.parse_qs(parsed.query)
                token = query.get("token", [""])[0]
                target = self.app.resolve_download(token)
                self._send_file(target, download=True)
                return
            self._serve_static(parsed.path)
        except ValueError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error_json(HTTPStatus.NOT_FOUND, str(exc))
        except RuntimeError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except ProviderError as exc:
            self._send_error_json(HTTPStatus.BAD_GATEWAY, str(exc))
        except Exception as exc:
            print(f"Web request failed: {exc}", file=sys.stderr)
            self._send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "服务器处理失败，请检查终端日志。",
            )

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/run":
            self._send_error_json(HTTPStatus.NOT_FOUND, "接口不存在。")
            return

        self.app.cleanup_expired_outputs()
        decision = self.app.allow_run(self._client_ip())
        if not decision.allowed:
            self._send_error_json(
                HTTPStatus.TOO_MANY_REQUESTS,
                decision.message or "公开演示请求过于频繁，请稍后再试。",
                headers=(
                    {"Retry-After": str(decision.retry_after)}
                    if decision.retry_after
                    else None
                ),
            )
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "请求长度无效。")
            return
        if length <= 0:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "请求内容为空。")
            return
        if length > self.app.max_upload_bytes:
            limit_mb = max(
                1,
                (self.app.max_upload_bytes + 1024 * 1024 - 1)
                // (1024 * 1024),
            )
            self._send_error_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                f"文件过大，当前上限为 {limit_mb} MB。",
            )
            return

        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        if not self.app.acquire_run_slot():
            self._send_error_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "当前演示任务较多，请稍后再试。",
                headers={"Retry-After": "5"},
            )
            return
        try:
            fields, files = parse_multipart(body, content_type)
            payload = self.app.run_payload(fields, files)
            self._send_json(payload)
        except ValueError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error_json(HTTPStatus.NOT_FOUND, str(exc))
        except RuntimeError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except ProviderError as exc:
            self._send_error_json(HTTPStatus.BAD_GATEWAY, str(exc))
        except Exception as exc:
            print(f"Web run failed: {exc}", file=sys.stderr)
            self._send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "处理失败，请检查终端日志。",
            )
        finally:
            self.app.release_run_slot()

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        root = self.app.static_dir.resolve()
        target = (root / relative).resolve()
        if target != root and root not in target.parents:
            raise ValueError("静态资源路径无效。")
        if not target.is_file():
            raise FileNotFoundError("页面资源不存在。")
        self._send_file(target, download=False)

    def _send_file(self, path: Path, download: bool) -> None:
        content = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self._send_security_headers(content_type)
        if download:
            encoded = urllib.parse.quote(path.name)
            self.send_header(
                "Content-Disposition",
                f"attachment; filename*=UTF-8''{encoded}",
            )
        self.end_headers()
        self.wfile.write(content)

    def _send_json(
        self,
        payload: Any,
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self._send_security_headers("application/json; charset=utf-8")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(content)

    def _send_error_json(
        self,
        status: HTTPStatus,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._send_json({"error": message}, status=status, headers=headers)

    def _send_security_headers(self, content_type: str) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        if content_type.lower().startswith("text/html"):
            self.send_header("Content-Security-Policy", SECURITY_CSP)

    def _client_ip(self) -> str:
        for header in ("CF-Connecting-IP", "X-Real-IP"):
            value = self.headers.get(header, "").strip()
            if value:
                return value
        forwarded = self.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
        return self.client_address[0]

    def log_message(self, format: str, *args: Any) -> None:
        request_path = urllib.parse.urlsplit(self.path).path
        print(
            f"{self._client_ip()} - {self.command} {request_path}",
            file=sys.stderr,
        )


class AppHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    app: WebApp
    cleanup_stop: threading.Event
    cleanup_thread: threading.Thread | None = None

    def server_close(self) -> None:
        stop = getattr(self, "cleanup_stop", None)
        if stop is not None:
            stop.set()
        thread = getattr(self, "cleanup_thread", None)
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=2)
        super().server_close()


def parse_multipart(
    body: bytes,
    content_type: str,
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    if "multipart/form-data" not in content_type.lower():
        raise ValueError("请求必须使用 multipart/form-data。")
    envelope = (
        f"Content-Type: {content_type}\r\n"
        "MIME-Version: 1.0\r\n\r\n"
    ).encode("utf-8") + body
    message = BytesParser(policy=policy.default).parsebytes(envelope)
    if not message.is_multipart():
        raise ValueError("无法解析上传内容。")

    fields: dict[str, str] = {}
    files: dict[str, dict[str, Any]] = {}
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        field_name = part.get_param("name", header="content-disposition")
        if not field_name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files[str(field_name)] = {
                "filename": _safe_filename(filename),
                "content": payload,
            }
            continue
        charset = part.get_content_charset() or "utf-8"
        try:
            fields[str(field_name)] = payload.decode(
                charset,
                errors="replace",
            )
        except LookupError as exc:
            raise ValueError("上传文本使用了不支持的字符编码。") from exc
    return fields, files


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    output_dir: str | Path = "outputs/web",
    static_dir: str | Path | None = None,
    examples_dir: str | Path = "examples",
    provider_name: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    public_demo: bool = False,
    retention_seconds: int | None = None,
    max_runs_per_window: int | None = None,
    max_runs_per_day: int | None = None,
    global_runs_per_day: int | None = None,
    max_concurrent_runs: int | None = None,
    max_upload_bytes: int | None = None,
    max_input_chars: int | None = None,
    quota_db_path: str | Path | None = None,
) -> AppHTTPServer:
    settings = Settings.from_env()
    package_root = Path(__file__).resolve().parent
    app = WebApp(
        output_dir=Path(output_dir),
        static_dir=Path(static_dir) if static_dir else package_root / "web_static",
        examples_dir=Path(examples_dir),
        provider_name=(
            provider_name if provider_name is not None else settings.provider
        ),
        model=model if model is not None else settings.model,
        base_url=base_url if base_url is not None else settings.base_url,
        public_demo=public_demo,
        public_allow_model=settings.public_allow_model,
        retention_seconds=(
            retention_seconds
            if retention_seconds is not None
            else settings.output_ttl_seconds
        ),
        max_runs_per_window=(
            max_runs_per_window
            if max_runs_per_window is not None
            else settings.max_runs_per_window
        ),
        max_runs_per_day=(
            max_runs_per_day
            if max_runs_per_day is not None
            else settings.max_runs_per_day
        ),
        global_runs_per_day=(
            global_runs_per_day
            if global_runs_per_day is not None
            else settings.global_runs_per_day
        ),
        max_concurrent_runs=(
            max_concurrent_runs
            if max_concurrent_runs is not None
            else settings.max_concurrent_runs
        ),
        max_upload_bytes=(
            max_upload_bytes
            if max_upload_bytes is not None
            else settings.max_upload_bytes
        ),
        max_input_chars=(
            max_input_chars
            if max_input_chars is not None
            else settings.max_input_chars
        ),
        max_output_tokens=settings.max_output_tokens,
        request_timeout_seconds=settings.request_timeout_seconds,
        quota_db_path=quota_db_path,
        api_key=settings.api_key,
    )
    server = AppHTTPServer((host, port), WebRequestHandler)
    server.app = app
    server.cleanup_stop = threading.Event()
    if app.retention_seconds > 0:
        interval = min(max(app.retention_seconds // 4, 5), 900)

        def cleanup_loop() -> None:
            while not server.cleanup_stop.wait(interval):
                app.cleanup_expired_outputs(force=True)

        server.cleanup_thread = threading.Thread(
            target=cleanup_loop,
            name="opc-output-cleanup",
            daemon=True,
        )
        server.cleanup_thread.start()
    return server


def build_parser() -> argparse.ArgumentParser:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(
        prog="opc-web",
        description="启动青年文书智能助手本地 Web 界面。",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--output-dir",
        default=settings.web_output_dir,
    )
    parser.add_argument("--examples-dir", default="examples")
    parser.add_argument(
        "--provider",
        choices=("mock", "deepseek", "openai", "openai-compatible"),
        default=settings.provider,
    )
    parser.add_argument("--model", default=settings.model)
    parser.add_argument("--base-url", default=settings.base_url)
    parser.add_argument(
        "--public-demo",
        action="store_true",
        default=settings.public_demo,
        help="启用公网演示限流、过期清理并强制使用本地规则。",
    )
    parser.add_argument(
        "--output-ttl-seconds",
        type=int,
        default=settings.output_ttl_seconds,
        help="运行结果保留秒数；0 表示不自动清理。",
    )
    parser.add_argument(
        "--max-runs-per-window",
        type=int,
        default=settings.max_runs_per_window,
        help="单个 IP 在限流窗口内的最大运行次数；0 表示不限制。",
    )
    parser.add_argument(
        "--max-runs-per-day",
        type=int,
        default=settings.max_runs_per_day,
        help="单个 IP 每日最大运行次数；0 表示不限制。",
    )
    parser.add_argument(
        "--global-runs-per-day",
        type=int,
        default=settings.global_runs_per_day,
        help="全站每日最大运行次数；0 表示不限制。",
    )
    parser.add_argument(
        "--max-concurrent-runs",
        type=int,
        default=settings.max_concurrent_runs,
        help="同时运行的最大任务数。",
    )
    parser.add_argument(
        "--max-upload-mb",
        type=int,
        default=settings.max_upload_mb,
        help="上传正文的文件大小上限，单位 MB。",
    )
    parser.add_argument(
        "--max-input-chars",
        type=int,
        default=settings.max_input_chars,
        help="单次处理的字符上限；0 表示不限制。",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="启动后自动打开浏览器。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    args = build_parser().parse_args(argv)
    try:
        server = create_server(
            host=args.host,
            port=args.port,
            output_dir=args.output_dir,
            examples_dir=args.examples_dir,
            provider_name=args.provider,
            model=args.model,
            base_url=args.base_url,
            public_demo=args.public_demo,
            retention_seconds=args.output_ttl_seconds,
            max_runs_per_window=args.max_runs_per_window,
            max_runs_per_day=args.max_runs_per_day,
            global_runs_per_day=args.global_runs_per_day,
            max_concurrent_runs=args.max_concurrent_runs,
            max_upload_bytes=args.max_upload_mb * 1024 * 1024,
            max_input_chars=args.max_input_chars,
        )
    except (OSError, ValueError) as exc:
        print(f"无法启动 Web 服务：{exc}", file=sys.stderr)
        return 2

    host, port = server.server_address[:2]
    url = f"http://{host}:{port}/"
    print(f"青年文书智能助手 Web: {url}")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止 Web 服务。")
    finally:
        server.server_close()
    return 0


def _b64url_encode(value: bytes) -> bytes:
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _safe_filename(value: str) -> str:
    return value.replace("\\", "/").rsplit("/", 1)[-1]


if __name__ == "__main__":
    raise SystemExit(main())
