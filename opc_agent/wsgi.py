"""WSGI adapter for hosting the youth document web workbench."""

from __future__ import annotations

import json
import mimetypes
import sys
import urllib.parse
from collections.abc import Callable, Iterable
from http import HTTPStatus
from pathlib import Path
from typing import Any

from opc_agent.config import Settings
from opc_agent.providers import ProviderError
from opc_agent.web import SECURITY_CSP, WebApp, parse_multipart


StartResponse = Callable[[str, list[tuple[str, str]]], Any]
WSGIEnviron = dict[str, Any]
WSGIResponse = Iterable[bytes]


class WSGIApplication:
    """Translate the standard-library web app into a WSGI callable."""

    def __init__(self, app: WebApp, url_prefix: str = "") -> None:
        self.app = app
        self.url_prefix = _normalize_prefix(url_prefix)

    def __call__(
        self,
        environ: WSGIEnviron,
        start_response: StartResponse,
    ) -> WSGIResponse:
        try:
            return self._dispatch(environ, start_response)
        except ValueError as exc:
            return _json_response(
                {"error": str(exc)},
                HTTPStatus.BAD_REQUEST,
                start_response,
            )
        except FileNotFoundError as exc:
            return _json_response(
                {"error": str(exc)},
                HTTPStatus.NOT_FOUND,
                start_response,
            )
        except RuntimeError as exc:
            return _json_response(
                {"error": str(exc)},
                HTTPStatus.BAD_REQUEST,
                start_response,
            )
        except ProviderError as exc:
            return _json_response(
                {"error": str(exc)},
                HTTPStatus.BAD_GATEWAY,
                start_response,
            )
        except Exception as exc:
            print(f"WSGI request failed: {exc}", file=sys.stderr)
            return _json_response(
                {"error": "服务器处理失败，请检查日志。"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
                start_response,
            )

    def _dispatch(
        self,
        environ: WSGIEnviron,
        start_response: StartResponse,
    ) -> WSGIResponse:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = _strip_prefix(
            str(environ.get("PATH_INFO") or "/"),
            self.url_prefix,
        )
        query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING") or ""))

        if method in {"GET", "HEAD"}:
            return self._handle_get(path, query, start_response, head=method == "HEAD")
        if method == "POST":
            return self._handle_post(environ, path, start_response)
        return _json_response(
            {"error": "请求方法不受支持。"},
            HTTPStatus.METHOD_NOT_ALLOWED,
            start_response,
            headers={"Allow": "GET, HEAD, POST"},
        )

    def _handle_get(
        self,
        path: str,
        query: dict[str, list[str]],
        start_response: StartResponse,
        *,
        head: bool,
    ) -> WSGIResponse:
        self.app.cleanup_expired_outputs()
        if path == "/api/health":
            return _json_response(
                self.app.health_payload(),
                HTTPStatus.OK,
                start_response,
                head=head,
            )
        if path == "/api/examples":
            task_value = query.get("task", ["contract"])[0]
            return _json_response(
                self.app.example_payload(task_value),
                HTTPStatus.OK,
                start_response,
                head=head,
            )
        if path == "/api/download":
            token = query.get("token", [""])[0]
            target = self.app.resolve_download(token)
            return _file_response(
                target,
                start_response,
                download=True,
                head=head,
            )
        return self._serve_static(path, start_response, head=head)

    def _handle_post(
        self,
        environ: WSGIEnviron,
        path: str,
        start_response: StartResponse,
    ) -> WSGIResponse:
        if path != "/api/run":
            raise FileNotFoundError("接口不存在。")

        self.app.cleanup_expired_outputs()
        client_ip = _client_ip(environ)
        decision = self.app.allow_run(client_ip)
        if not decision.allowed:
            return _json_response(
                {
                    "error": (
                        decision.message
                        or "公开演示请求过于频繁，请稍后再试。"
                    )
                },
                HTTPStatus.TOO_MANY_REQUESTS,
                start_response,
                headers=(
                    {"Retry-After": str(decision.retry_after)}
                    if decision.retry_after
                    else None
                ),
            )

        content_length_raw = str(environ.get("CONTENT_LENGTH") or "").strip()
        if not content_length_raw:
            return _json_response(
                {"error": "请求缺少 Content-Length。"},
                HTTPStatus.LENGTH_REQUIRED,
                start_response,
            )
        try:
            content_length = int(content_length_raw)
        except ValueError:
            return _json_response(
                {"error": "请求长度无效。"},
                HTTPStatus.BAD_REQUEST,
                start_response,
            )
        if content_length <= 0:
            return _json_response(
                {"error": "请求内容为空。"},
                HTTPStatus.BAD_REQUEST,
                start_response,
            )
        if content_length > self.app.max_upload_bytes:
            limit_mb = max(
                1,
                (self.app.max_upload_bytes + 1024 * 1024 - 1) // (1024 * 1024),
            )
            return _json_response(
                {"error": f"文件过大，当前上限为 {limit_mb} MB。"},
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                start_response,
            )

        if not self.app.acquire_run_slot():
            return _json_response(
                {"error": "当前演示任务较多，请稍后再试。"},
                HTTPStatus.SERVICE_UNAVAILABLE,
                start_response,
                headers={"Retry-After": "5"},
            )
        try:
            body = environ["wsgi.input"].read(content_length)
            content_type = str(environ.get("CONTENT_TYPE") or "")
            fields, files = parse_multipart(body, content_type)
            return _json_response(
                self.app.run_payload(fields, files),
                HTTPStatus.OK,
                start_response,
            )
        finally:
            self.app.release_run_slot()

    def _serve_static(
        self,
        request_path: str,
        start_response: StartResponse,
        *,
        head: bool,
    ) -> WSGIResponse:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        root = self.app.static_dir.resolve()
        target = (root / relative).resolve()
        if target != root and root not in target.parents:
            raise ValueError("静态资源路径无效。")
        if not target.is_file():
            raise FileNotFoundError("页面资源不存在。")
        return _file_response(target, start_response, download=False, head=head)


def create_application(
    project_root: str | Path,
    *,
    output_dir: str | Path | None = None,
    static_dir: str | Path | None = None,
    examples_dir: str | Path | None = None,
    provider_name: str | None = None,
    model: str | None = None,
    public_demo: bool | None = None,
    public_allow_model: bool | None = None,
    retention_seconds: int | None = None,
    max_runs_per_window: int | None = None,
    max_runs_per_day: int | None = None,
    global_runs_per_day: int | None = None,
    max_concurrent_runs: int | None = None,
    max_upload_bytes: int | None = None,
    max_input_chars: int | None = None,
    max_output_tokens: int | None = None,
    request_timeout_seconds: int | None = None,
    quota_db_path: str | Path | None = None,
    url_prefix: str = "",
) -> WSGIApplication:
    root = Path(project_root).resolve()
    settings = Settings.from_env()
    resolved_public_demo = (
        settings.public_demo if public_demo is None else bool(public_demo)
    )
    resolved_provider = (
        provider_name if provider_name is not None else settings.provider
    )
    resolved_model = model if model is not None else settings.model
    resolved_base_url = settings.base_url
    resolved_api_key = settings.api_key
    resolved_public_allow_model = (
        settings.public_allow_model
        if public_allow_model is None
        else bool(public_allow_model)
    )
    if (
        resolved_public_demo
        and provider_name is None
        and resolved_provider != "mock"
        and not resolved_public_allow_model
    ):
        resolved_provider = "mock"
        resolved_model = ""
        resolved_base_url = ""
        resolved_api_key = ""
    app = WebApp(
        output_dir=(
            Path(output_dir)
            if output_dir is not None
            else root / settings.web_output_dir
        ),
        static_dir=(
            Path(static_dir)
            if static_dir is not None
            else Path(__file__).resolve().parent / "web_static"
        ),
        examples_dir=(
            Path(examples_dir) if examples_dir is not None else root / "examples"
        ),
        provider_name=resolved_provider,
        model=resolved_model,
        public_demo=resolved_public_demo,
        public_allow_model=resolved_public_allow_model,
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
        max_output_tokens=(
            max_output_tokens
            if max_output_tokens is not None
            else settings.max_output_tokens
        ),
        request_timeout_seconds=(
            request_timeout_seconds
            if request_timeout_seconds is not None
            else settings.request_timeout_seconds
        ),
        quota_db_path=quota_db_path,
        url_prefix=url_prefix,
        base_url=resolved_base_url,
        api_key=resolved_api_key,
    )
    return WSGIApplication(app, url_prefix=url_prefix)


def _strip_prefix(path: str, prefix: str) -> str:
    if not prefix:
        return path or "/"
    if path == prefix:
        return "/"
    if path.startswith(f"{prefix}/"):
        return path[len(prefix) :]
    raise FileNotFoundError("页面资源不存在。")


def _normalize_prefix(value: str) -> str:
    prefix = value.strip().rstrip("/")
    if prefix == "/":
        return ""
    if prefix and not prefix.startswith("/"):
        return f"/{prefix}"
    return prefix


def _client_ip(environ: WSGIEnviron) -> str:
    # Trust the server-provided peer address. Forwarded headers are
    # client-controlled unless a trusted reverse proxy overwrites them.
    return str(environ.get("REMOTE_ADDR") or "unknown").strip() or "unknown"


def _json_response(
    payload: Any,
    status: HTTPStatus,
    start_response: StartResponse,
    *,
    headers: dict[str, str] | None = None,
    head: bool = False,
) -> WSGIResponse:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    response_headers = _security_headers("application/json; charset=utf-8")
    response_headers.extend(
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
        ]
    )
    response_headers.extend((headers or {}).items())
    start_response(f"{status.value} {status.phrase}", response_headers)
    return [b"" if head else body]


def _file_response(
    path: Path,
    start_response: StartResponse,
    *,
    download: bool,
    head: bool = False,
) -> WSGIResponse:
    body = path.read_bytes()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    response_headers = _security_headers(content_type)
    response_headers.extend(
        [
            ("Content-Type", content_type),
            ("Content-Length", str(len(body))),
        ]
    )
    if download:
        encoded = urllib.parse.quote(path.name)
        response_headers.append(
            (
                "Content-Disposition",
                f"attachment; filename*=UTF-8''{encoded}",
            )
        )
    start_response(f"{HTTPStatus.OK.value} {HTTPStatus.OK.phrase}", response_headers)
    return [b"" if head else body]


def _security_headers(content_type: str) -> list[tuple[str, str]]:
    headers = [
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Referrer-Policy", "no-referrer"),
        ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
        ("Cross-Origin-Resource-Policy", "same-origin"),
    ]
    if content_type.lower().startswith("text/html"):
        headers.append(("Content-Security-Policy", SECURITY_CSP))
    return headers
