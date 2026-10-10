import io
import json
import sys
import types
import unittest
import urllib.error
from unittest import mock

from opc_agent.providers import (
    DeepSeekProvider,
    MockProvider,
    OpenAICompatibleProvider,
    ProviderError,
    create_provider,
)


class OpenAICompatibleProviderTests(unittest.TestCase):
    def _fake_openai_module(self, create):
        calls = []

        class FakeCompletions:
            def create(self, **kwargs):
                calls.append(kwargs)
                return create(**kwargs)

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.chat = FakeChat()

        module = types.ModuleType("openai")
        module.OpenAI = FakeClient
        return module, calls

    def test_complete_uses_configured_chat_endpoint(self):
        def response(**kwargs):
            message = types.SimpleNamespace(content='{"ok": true}')
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=message)]
            )

        module, calls = self._fake_openai_module(response)
        provider = OpenAICompatibleProvider(
            model="model-name",
            api_key="secret",
            base_url="https://example.test/v1",
        )

        with mock.patch.dict(sys.modules, {"openai": module}):
            result = provider.complete("system", "user")

        self.assertEqual(result, '{"ok": true}')
        self.assertEqual(
            calls,
            [
                {
                    "model": "model-name",
                    "messages": [
                        {"role": "system", "content": "system"},
                        {"role": "user", "content": "user"},
                    ],
                    "temperature": 0.2,
                }
            ],
        )

    def test_complete_wraps_sdk_errors_for_rule_fallback(self):
        def response(**kwargs):
            raise RuntimeError("network down")

        module, _ = self._fake_openai_module(response)
        provider = OpenAICompatibleProvider(
            model="model-name",
            api_key="secret",
            base_url="https://example.test/v1",
        )

        with mock.patch.dict(sys.modules, {"openai": module}):
            with self.assertRaisesRegex(ProviderError, "network down"):
                provider.complete("system", "user")

    def test_factory_builds_supported_providers(self):
        self.assertIsInstance(create_provider("mock"), MockProvider)
        self.assertIsInstance(
            create_provider(
                "openai-compatible",
                model="model-name",
                base_url="https://example.test/v1",
            ),
            OpenAICompatibleProvider,
        )
        self.assertIsInstance(
            create_provider(
                "deepseek",
                model="deepseek-chat",
                api_key="secret",
            ),
            DeepSeekProvider,
        )
        with self.assertRaisesRegex(ProviderError, "不支持的 Provider"):
            create_provider("unknown")


class DeepSeekProviderTests(unittest.TestCase):
    def test_complete_posts_openai_compatible_payload(self):
        response_body = json.dumps(
            {
                "choices": [
                    {"message": {"content": '{"ok": true}'}},
                ]
            }
        ).encode("utf-8")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return response_body

        provider = DeepSeekProvider(
            model="deepseek-chat",
            api_key="secret",
            max_tokens=512,
            timeout_seconds=12,
        )
        with mock.patch(
            "opc_agent.providers.deepseek.urllib.request.urlopen",
            return_value=FakeResponse(),
        ) as urlopen:
            result = provider.complete("system", "user")

        self.assertEqual(result, '{"ok": true}')
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://api.deepseek.com/chat/completions",
        )
        self.assertEqual(
            request.get_header("Authorization"),
            "Bearer secret",
        )
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "deepseek-chat")
        self.assertEqual(payload["max_tokens"], 512)
        self.assertEqual(
            payload["messages"][0],
            {"role": "system", "content": "system"},
        )
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 12)

    def test_http_error_redacts_api_key(self):
        error = urllib.error.HTTPError(
            "https://api.deepseek.com/chat/completions",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":{"message":"bad key secret"}}'),
        )
        provider = DeepSeekProvider(
            model="deepseek-chat",
            api_key="secret",
        )

        with mock.patch(
            "opc_agent.providers.deepseek.urllib.request.urlopen",
            side_effect=error,
        ):
            with self.assertRaises(ProviderError) as context:
                provider.complete("system", "user")

        self.assertIn("[redacted]", str(context.exception))
        self.assertNotIn("secret", str(context.exception))


if __name__ == "__main__":
    unittest.main()
