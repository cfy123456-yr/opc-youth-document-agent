from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class QuotaDecision:
    allowed: bool
    message: str = ""
    retry_after: int = 0


class UsageQuota:
    """Persistent daily quota shared by all workers using the same database."""

    def __init__(
        self,
        path: str | Path,
        *,
        per_ip_limit: int,
        global_limit: int,
    ) -> None:
        self.path = Path(path)
        self.per_ip_limit = max(0, int(per_ip_limit))
        self.global_limit = max(0, int(global_limit))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @property
    def enabled(self) -> bool:
        return self.per_ip_limit > 0 or self.global_limit > 0

    def try_consume(self, client_ip: str) -> QuotaDecision:
        if not self.enabled:
            return QuotaDecision(True)

        day = datetime.now(timezone.utc).date().isoformat()
        client_key = hashlib.sha256(
            client_ip.strip().encode("utf-8", errors="replace")
        ).hexdigest()[:32]
        try:
            with closing(
                sqlite3.connect(
                    self.path,
                    timeout=5,
                    isolation_level=None,
                )
            ) as connection:
                connection.execute("PRAGMA busy_timeout = 5000")
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "DELETE FROM run_usage WHERE day < date(?, '-7 day')",
                    (day,),
                )
                global_count = self._count(connection, day, "global", "all")
                ip_count = self._count(connection, day, "ip", client_key)

                if (
                    self.global_limit > 0
                    and global_count >= self.global_limit
                ):
                    connection.rollback()
                    return QuotaDecision(
                        False,
                        "今日全站 AI 处理额度已用完，请明天再试或使用本地规则。",
                    )
                if self.per_ip_limit > 0 and ip_count >= self.per_ip_limit:
                    connection.rollback()
                    return QuotaDecision(
                        False,
                        "你今天的 AI 处理额度已用完，请明天再试或使用本地规则。",
                    )

                self._increment(connection, day, "global", "all")
                self._increment(connection, day, "ip", client_key)
                connection.commit()
        except sqlite3.Error:
            return QuotaDecision(
                False,
                "额度检查暂时不可用，为保护服务已暂停 AI 调用。",
                retry_after=30,
            )
        return QuotaDecision(True)

    def _initialize(self) -> None:
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS run_usage (
                    day TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (day, scope, subject)
                )
                """
            )
            connection.commit()

    @staticmethod
    def _count(
        connection: sqlite3.Connection,
        day: str,
        scope: str,
        subject: str,
    ) -> int:
        row = connection.execute(
            """
            SELECT count FROM run_usage
            WHERE day = ? AND scope = ? AND subject = ?
            """,
            (day, scope, subject),
        ).fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def _increment(
        connection: sqlite3.Connection,
        day: str,
        scope: str,
        subject: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO run_usage (day, scope, subject, count, updated_at)
            VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(day, scope, subject) DO UPDATE SET
                count = count + 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (day, scope, subject),
        )
