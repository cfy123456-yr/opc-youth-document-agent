"""PythonAnywhere WSGI entry point with the youth app mounted at /youth."""

from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any


YOUTH_PREFIX = "/youth"
YOUTH_ROOT = Path.home() / "opc-youth-document-agent"
YOUTH_DATA_ROOT = Path.home() / "opc-youth-data"
EXISTING_ROOT = Path.home() / "gaoshu-agent"

for project_root in (str(YOUTH_ROOT), str(EXISTING_ROOT)):
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(EXISTING_ROOT / ".env", override=True)

os.environ.setdefault("LOG_ENABLED", "false")
os.environ.setdefault("CALCULATION_TIMEOUT_SECONDS", "20")
os.environ.setdefault("CALCULATION_WORKERS", "2")
os.environ["OPC_PROVIDER"] = "mock"
os.environ["OPC_MODEL"] = ""

from opc_agent.wsgi import create_application


youth_application = create_application(
    YOUTH_ROOT,
    output_dir=YOUTH_DATA_ROOT / "outputs",
    public_demo=True,
    retention_seconds=3600,
    max_runs_per_window=12,
    max_concurrent_runs=2,
    max_upload_bytes=15 * 1024 * 1024,
    url_prefix=YOUTH_PREFIX,
)


def _load_existing_application() -> Callable[[dict[str, Any], Any], Iterable[bytes]]:
    module_path = EXISTING_ROOT / "deploy" / "wsgi_app.py"
    spec = importlib.util.spec_from_file_location(
        "legacy_gaoshu_wsgi_application",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载现有 WSGI 应用：{module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.application


existing_application = _load_existing_application()


def application(environ: dict[str, Any], start_response: Any) -> Iterable[bytes]:
    path = str(environ.get("PATH_INFO") or "/")
    if path == YOUTH_PREFIX:
        query = str(environ.get("QUERY_STRING") or "")
        location = f"{YOUTH_PREFIX}/"
        if query:
            location = f"{location}?{query}"
        start_response(
            "308 Permanent Redirect",
            [
                ("Location", location),
                ("Content-Length", "0"),
            ],
        )
        return [b""]
    if path.startswith(f"{YOUTH_PREFIX}/"):
        return youth_application(environ, start_response)
    return existing_application(environ, start_response)
