"""Standalone PythonAnywhere WSGI entry point for the document workbench."""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path.home() / "opc-youth-document-agent"
DATA_ROOT = Path.home() / "opc-youth-data"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LOG_ENABLED", "false")
os.environ.setdefault("CALCULATION_TIMEOUT_SECONDS", "20")
os.environ.setdefault("CALCULATION_WORKERS", "2")

from opc_agent.wsgi import create_application


application = create_application(
    PROJECT_ROOT,
    output_dir=DATA_ROOT / "outputs",
    public_demo=True,
    public_allow_model=True,
    retention_seconds=3600,
    max_runs_per_window=12,
    max_runs_per_day=6,
    global_runs_per_day=30,
    max_concurrent_runs=2,
    max_upload_bytes=15 * 1024 * 1024,
    max_input_chars=20000,
    max_output_tokens=1600,
    request_timeout_seconds=45,
    quota_db_path=DATA_ROOT / "usage.sqlite3",
)
