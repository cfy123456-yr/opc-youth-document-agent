from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_PROVIDER = "mock"
DEFAULT_MODEL = ""
DEFAULT_BASE_URL = ""
DEFAULT_OUTPUT_DIR = "outputs"
DEFAULT_WEB_OUTPUT_DIR = "outputs/web"
DEFAULT_PUBLIC_DEMO = False
DEFAULT_OUTPUT_TTL_SECONDS = 0
DEFAULT_MAX_RUNS_PER_WINDOW = 0
DEFAULT_MAX_RUNS_PER_DAY = 0
DEFAULT_GLOBAL_RUNS_PER_DAY = 0
DEFAULT_MAX_CONCURRENT_RUNS = 2
DEFAULT_MAX_UPLOAD_MB = 15
DEFAULT_MAX_INPUT_CHARS = 0
DEFAULT_MAX_OUTPUT_TOKENS = 0
DEFAULT_REQUEST_TIMEOUT_SECONDS = 45
DEFAULT_MAX_UPLOAD_BYTES = DEFAULT_MAX_UPLOAD_MB * 1024 * 1024

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def read_env_file(path: str | Path | None = None) -> dict[str, str]:
    env_path = (
        Path(path)
        if path is not None
        else Path(__file__).resolve().parents[1] / ".env"
    )
    if not env_path.is_file():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(
        encoding="utf-8-sig",
        errors="replace",
    ).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        if not separator:
            continue
        name = name.strip()
        if not name:
            continue
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        values[name] = value
    return values


def read_env_text(
    name: str,
    default: str = "",
    *,
    env: Mapping[str, str] | None = None,
) -> str:
    values = os.environ if env is None else env
    value = values.get(name)
    return default if value is None else value


def read_env_int(
    name: str,
    default: int,
    *,
    env: Mapping[str, str] | None = None,
) -> int:
    raw = read_env_text(name, "", env=env).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def read_env_flag(
    name: str,
    default: bool = False,
    *,
    env: Mapping[str, str] | None = None,
) -> bool:
    raw = read_env_text(name, "", env=env).strip().lower()
    if not raw:
        return default
    return raw in _TRUE_VALUES


@dataclass(frozen=True, slots=True)
class Settings:
    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    output_dir: str = DEFAULT_OUTPUT_DIR
    web_output_dir: str = DEFAULT_WEB_OUTPUT_DIR
    public_demo: bool = DEFAULT_PUBLIC_DEMO
    public_allow_model: bool = False
    output_ttl_seconds: int = DEFAULT_OUTPUT_TTL_SECONDS
    max_runs_per_window: int = DEFAULT_MAX_RUNS_PER_WINDOW
    max_runs_per_day: int = DEFAULT_MAX_RUNS_PER_DAY
    global_runs_per_day: int = DEFAULT_GLOBAL_RUNS_PER_DAY
    max_concurrent_runs: int = DEFAULT_MAX_CONCURRENT_RUNS
    max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    request_timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS
    api_key: str = field(default="", repr=False)

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
    ) -> Settings:
        if env is None:
            environment = read_env_file()
            environment.update(os.environ)
        else:
            environment = env
        return cls(
            provider=read_env_text(
                "OPC_PROVIDER",
                DEFAULT_PROVIDER,
                env=environment,
            ),
            model=read_env_text("OPC_MODEL", DEFAULT_MODEL, env=environment),
            base_url=read_env_text(
                "OPC_BASE_URL",
                DEFAULT_BASE_URL,
                env=environment,
            ),
            output_dir=read_env_text(
                "OPC_OUTPUT_DIR",
                DEFAULT_OUTPUT_DIR,
                env=environment,
            ),
            web_output_dir=read_env_text(
                "OPC_WEB_OUTPUT_DIR",
                DEFAULT_WEB_OUTPUT_DIR,
                env=environment,
            ),
            public_demo=read_env_flag(
                "OPC_PUBLIC_DEMO",
                DEFAULT_PUBLIC_DEMO,
                env=environment,
            ),
            public_allow_model=read_env_flag(
                "OPC_PUBLIC_ALLOW_MODEL",
                False,
                env=environment,
            ),
            output_ttl_seconds=read_env_int(
                "OPC_OUTPUT_TTL_SECONDS",
                DEFAULT_OUTPUT_TTL_SECONDS,
                env=environment,
            ),
            max_runs_per_window=read_env_int(
                "OPC_MAX_RUNS_PER_WINDOW",
                DEFAULT_MAX_RUNS_PER_WINDOW,
                env=environment,
            ),
            max_runs_per_day=read_env_int(
                "OPC_MAX_RUNS_PER_DAY",
                DEFAULT_MAX_RUNS_PER_DAY,
                env=environment,
            ),
            global_runs_per_day=read_env_int(
                "OPC_GLOBAL_RUNS_PER_DAY",
                DEFAULT_GLOBAL_RUNS_PER_DAY,
                env=environment,
            ),
            max_concurrent_runs=read_env_int(
                "OPC_MAX_CONCURRENT_RUNS",
                DEFAULT_MAX_CONCURRENT_RUNS,
                env=environment,
            ),
            max_upload_mb=read_env_int(
                "OPC_MAX_UPLOAD_MB",
                DEFAULT_MAX_UPLOAD_MB,
                env=environment,
            ),
            max_input_chars=read_env_int(
                "OPC_MAX_INPUT_CHARS",
                DEFAULT_MAX_INPUT_CHARS,
                env=environment,
            ),
            max_output_tokens=read_env_int(
                "OPC_MAX_OUTPUT_TOKENS",
                DEFAULT_MAX_OUTPUT_TOKENS,
                env=environment,
            ),
            request_timeout_seconds=read_env_int(
                "OPC_REQUEST_TIMEOUT_SECONDS",
                DEFAULT_REQUEST_TIMEOUT_SECONDS,
                env=environment,
            ),
            api_key=(
                read_env_text("OPC_API_KEY", "", env=environment)
                or read_env_text("OPENAI_API_KEY", "", env=environment)
            ),
        )

    @property
    def max_upload_bytes(self) -> int:
        return max(1, self.max_upload_mb) * 1024 * 1024

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key.strip())

    @property
    def has_openai_api_key(self) -> bool:
        return self.has_api_key
