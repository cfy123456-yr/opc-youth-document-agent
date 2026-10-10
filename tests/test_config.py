import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from opc_agent.config import (
    Settings,
    read_env_file,
    read_env_flag,
    read_env_int,
)


class SettingsTests(unittest.TestCase):
    def test_defaults_are_centralized(self):
        settings = Settings.from_env({})

        self.assertEqual(settings.provider, "mock")
        self.assertEqual(settings.base_url, "")
        self.assertEqual(settings.output_dir, "outputs")
        self.assertEqual(settings.web_output_dir, "outputs/web")
        self.assertFalse(settings.public_demo)
        self.assertEqual(settings.max_concurrent_runs, 2)
        self.assertEqual(settings.max_upload_bytes, 15 * 1024 * 1024)
        self.assertFalse(settings.public_allow_model)
        self.assertEqual(settings.max_runs_per_day, 0)
        self.assertEqual(settings.global_runs_per_day, 0)
        self.assertEqual(settings.max_input_chars, 0)
        self.assertEqual(settings.max_output_tokens, 0)
        self.assertEqual(settings.request_timeout_seconds, 45)
        self.assertFalse(settings.has_api_key)

    def test_values_are_read_from_environment(self):
        settings = Settings.from_env(
            {
                "OPC_PROVIDER": "openai",
                "OPC_MODEL": "test-model",
                "OPC_BASE_URL": "https://example.test/v1",
                "OPC_OUTPUT_DIR": "custom-outputs",
                "OPC_WEB_OUTPUT_DIR": "custom-web-outputs",
                "OPC_PUBLIC_DEMO": "yes",
                "OPC_PUBLIC_ALLOW_MODEL": "true",
                "OPC_OUTPUT_TTL_SECONDS": "120",
                "OPC_MAX_RUNS_PER_WINDOW": "7",
                "OPC_MAX_RUNS_PER_DAY": "6",
                "OPC_GLOBAL_RUNS_PER_DAY": "30",
                "OPC_MAX_CONCURRENT_RUNS": "3",
                "OPC_MAX_UPLOAD_MB": "5",
                "OPC_MAX_INPUT_CHARS": "20000",
                "OPC_MAX_OUTPUT_TOKENS": "1600",
                "OPC_REQUEST_TIMEOUT_SECONDS": "45",
                "OPC_API_KEY": "secret",
            }
        )

        self.assertEqual(settings.provider, "openai")
        self.assertEqual(settings.model, "test-model")
        self.assertEqual(settings.base_url, "https://example.test/v1")
        self.assertEqual(settings.output_dir, "custom-outputs")
        self.assertEqual(settings.web_output_dir, "custom-web-outputs")
        self.assertTrue(settings.public_demo)
        self.assertTrue(settings.public_allow_model)
        self.assertEqual(settings.output_ttl_seconds, 120)
        self.assertEqual(settings.max_runs_per_window, 7)
        self.assertEqual(settings.max_runs_per_day, 6)
        self.assertEqual(settings.global_runs_per_day, 30)
        self.assertEqual(settings.max_concurrent_runs, 3)
        self.assertEqual(settings.max_upload_bytes, 5 * 1024 * 1024)
        self.assertEqual(settings.max_input_chars, 20000)
        self.assertEqual(settings.max_output_tokens, 1600)
        self.assertEqual(settings.request_timeout_seconds, 45)
        self.assertTrue(settings.has_api_key)
        self.assertTrue(settings.has_openai_api_key)
        self.assertNotIn("secret", repr(settings))

    def test_openai_api_key_remains_a_fallback(self):
        settings = Settings.from_env({"OPENAI_API_KEY": "legacy-secret"})

        self.assertTrue(settings.has_api_key)

    def test_env_file_parser_supports_quotes_and_comments(self):
        with TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# comment",
                        'OPC_PROVIDER="openai-compatible"',
                        "OPC_BASE_URL=https://api.deepseek.com",
                        "export OPC_MODEL='deepseek-chat'",
                        "INVALID_LINE",
                    ]
                ),
                encoding="utf-8",
            )

            values = read_env_file(env_path)

        self.assertEqual(values["OPC_PROVIDER"], "openai-compatible")
        self.assertEqual(values["OPC_BASE_URL"], "https://api.deepseek.com")
        self.assertEqual(values["OPC_MODEL"], "deepseek-chat")
        self.assertNotIn("INVALID_LINE", values)

    def test_invalid_values_fall_back_safely(self):
        self.assertEqual(read_env_int("OPC_VALUE", 9, env={"OPC_VALUE": "x"}), 9)
        self.assertFalse(
            read_env_flag(
                "OPC_VALUE",
                default=False,
                env={"OPC_VALUE": "invalid"},
            )
        )
        settings = Settings.from_env({"OPC_MAX_UPLOAD_MB": "-2"})
        self.assertEqual(settings.max_upload_bytes, 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
