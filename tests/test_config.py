import unittest

from opc_agent.config import Settings, read_env_flag, read_env_int


class SettingsTests(unittest.TestCase):
    def test_defaults_are_centralized(self):
        settings = Settings.from_env({})

        self.assertEqual(settings.provider, "mock")
        self.assertEqual(settings.output_dir, "outputs")
        self.assertEqual(settings.web_output_dir, "outputs/web")
        self.assertFalse(settings.public_demo)
        self.assertEqual(settings.max_concurrent_runs, 2)
        self.assertEqual(settings.max_upload_bytes, 15 * 1024 * 1024)
        self.assertFalse(settings.has_openai_api_key)

    def test_values_are_read_from_environment(self):
        settings = Settings.from_env(
            {
                "OPC_PROVIDER": "openai",
                "OPC_MODEL": "test-model",
                "OPC_OUTPUT_DIR": "custom-outputs",
                "OPC_WEB_OUTPUT_DIR": "custom-web-outputs",
                "OPC_PUBLIC_DEMO": "yes",
                "OPC_OUTPUT_TTL_SECONDS": "120",
                "OPC_MAX_RUNS_PER_WINDOW": "7",
                "OPC_MAX_CONCURRENT_RUNS": "3",
                "OPC_MAX_UPLOAD_MB": "5",
                "OPENAI_API_KEY": "secret",
            }
        )

        self.assertEqual(settings.provider, "openai")
        self.assertEqual(settings.model, "test-model")
        self.assertEqual(settings.output_dir, "custom-outputs")
        self.assertEqual(settings.web_output_dir, "custom-web-outputs")
        self.assertTrue(settings.public_demo)
        self.assertEqual(settings.output_ttl_seconds, 120)
        self.assertEqual(settings.max_runs_per_window, 7)
        self.assertEqual(settings.max_concurrent_runs, 3)
        self.assertEqual(settings.max_upload_bytes, 5 * 1024 * 1024)
        self.assertTrue(settings.has_openai_api_key)
        self.assertNotIn("secret", repr(settings))

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
