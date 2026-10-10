import tempfile
import unittest
from pathlib import Path

from opc_agent.quota import UsageQuota


class UsageQuotaTests(unittest.TestCase):
    def test_per_ip_limit_is_persistent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "usage.sqlite3"
            quota = UsageQuota(
                db_path,
                per_ip_limit=1,
                global_limit=10,
            )

            self.assertTrue(quota.try_consume("198.51.100.10").allowed)
            denied = quota.try_consume("198.51.100.10")
            self.assertFalse(denied.allowed)
            self.assertIn("今天的 AI 处理额度", denied.message)
            self.assertTrue(quota.try_consume("198.51.100.11").allowed)

            reloaded = UsageQuota(
                db_path,
                per_ip_limit=1,
                global_limit=10,
            )
            self.assertFalse(reloaded.try_consume("198.51.100.10").allowed)

    def test_global_limit_spans_all_ips(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            quota = UsageQuota(
                Path(temp_dir) / "usage.sqlite3",
                per_ip_limit=10,
                global_limit=2,
            )

            self.assertTrue(quota.try_consume("198.51.100.10").allowed)
            self.assertTrue(quota.try_consume("198.51.100.11").allowed)
            denied = quota.try_consume("198.51.100.12")
            self.assertFalse(denied.allowed)
            self.assertIn("全站 AI 处理额度", denied.message)

    def test_disabled_quota_allows_requests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            quota = UsageQuota(
                Path(temp_dir) / "usage.sqlite3",
                per_ip_limit=0,
                global_limit=0,
            )

            self.assertFalse(quota.enabled)
            self.assertTrue(quota.try_consume("198.51.100.10").allowed)


if __name__ == "__main__":
    unittest.main()
