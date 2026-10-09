from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field


DEFAULT_PROVIDER = "mock"
DEFAULT_MODEL = ""
DEFAULT_OUTPUT_DIR = "outputs"
DEFAULT_WEB_OUTPUT_DIR = "outputs/web"
DEFAULT_PUBLIC_DEMO = False
DEFAULT_OUTPUT_TTL_SECONDS = 0
DEFAULT_MAX_RUNS_PER_WINDOW = 0
DEFAULT_MAX_CONCURRENT_RUNS = 2
DEFAULT_MAX_UPLOAD_MB = 15
DEFAULT_MAX_UPLOAD_BYTES = DEFAULT_MAX_UPLOAD_MB * 1024 * 1024

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


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
    output_dir: str = DEFAULT_OUTPUT_DIR
    web_output_dir: str = DEFAULT_WEB_OUTPUT_DIR
    public_demo: bool = DEFAULT_PUBLIC_DEMO
    output_ttl_seconds: int = DEFAULT_OUTPUT_TTL_SECONDS
    max_runs_per_window: int = DEFAULT_MAX_RUNS_PER_WINDOW
    max_concurrent_runs: int = DEFAULT_MAX_CONCURRENT_RUNS
    max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB
    openai_api_key: str = field(default="", repr=False)

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
    ) -> Settings:
        return cls(
            provider=read_env_text(
                "OPC_PROVIDER",
                DEFAULT_PROVIDER,
                env=env,
            ),
            model=read_env_text("OPC_MODEL", DEFAULT_MODEL, env=env),
            output_dir=read_env_text(
                "OPC_OUTPUT_DIR",
                DEFAULT_OUTPUT_DIR,
                env=env,
            ),
            web_output_dir=read_env_text(
                "OPC_WEB_OUTPUT_DIR",
                DEFAULT_WEB_OUTPUT_DIR,
                env=env,
            ),
            public_demo=read_env_flag(
                "OPC_PUBLIC_DEMO",
                DEFAULT_PUBLIC_DEMO,
                env=env,
            ),
            output_ttl_seconds=read_env_int(
                "OPC_OUTPUT_TTL_SECONDS",
                DEFAULT_OUTPUT_TTL_SECONDS,
                env=env,
            ),
            max_runs_per_window=read_env_int(
                "OPC_MAX_RUNS_PER_WINDOW",
                DEFAULT_MAX_RUNS_PER_WINDOW,
                env=env,
            ),
            max_concurrent_runs=read_env_int(
                "OPC_MAX_CONCURRENT_RUNS",
                DEFAULT_MAX_CONCURRENT_RUNS,
                env=env,
            ),
            max_upload_mb=read_env_int(
                "OPC_MAX_UPLOAD_MB",
                DEFAULT_MAX_UPLOAD_MB,
                env=env,
            ),
            openai_api_key=read_env_text("OPENAI_API_KEY", "", env=env),
        )

    @property
    def max_upload_bytes(self) -> int:
        return max(1, self.max_upload_mb) * 1024 * 1024

    @property
    def has_openai_api_key(self) -> bool:
        return bool(self.openai_api_key.strip())
