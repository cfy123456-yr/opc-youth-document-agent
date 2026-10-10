from __future__ import annotations

import json
import urllib.error
import urllib.request

from opc_agent.providers.base import ModelProvider, ProviderError


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider(ModelProvider):
    """Minimal DeepSeek chat-completions client using the standard library."""

    name = "deepseek"

    def __init__(
        self,
        model: str = "deepseek-chat",
        api_key: str = "",
        base_url: str = DEFAULT_DEEPSEEK_BASE_URL,
        *,
        max_tokens: int = 0,
        temperature: float = 0.2,
        timeout_seconds: int = 45,
    ) -> None:
        self.model = model.strip() or "deepseek-chat"
        self.api_key = api_key.strip()
        self.base_url = (
            base_url.strip().rstrip("/") or DEFAULT_DEEPSEEK_BASE_URL
        )
        self.max_tokens = max(0, int(max_tokens))
        self.temperature = max(0.0, min(2.0, float(temperature)))
        self.timeout_seconds = max(5, int(timeout_seconds))

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.model)

    def complete(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self.available:
            raise ProviderError("第三方 AI 服务未配置。")

        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "stream": False,
        }
        if self.max_tokens > 0:
            payload["max_tokens"] = self.max_tokens

        request = urllib.request.Request(
            self._endpoint(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "opc-youth-document-agent/0.2",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = self._safe_error_detail(exc)
            raise ProviderError(
                f"第三方 AI 接口调用失败：HTTP {exc.code} {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError(
                f"第三方 AI 接口连接失败：{type(exc).__name__}"
            ) from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError("第三方 AI 接口返回了无法解析的数据。") from exc

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("第三方 AI 接口没有返回候选结果。")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return content
        raise ProviderError("第三方 AI 接口没有返回文本内容。")

    def _endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def _safe_error_detail(self, error: urllib.error.HTTPError) -> str:
        try:
            raw = error.read(2048).decode("utf-8", errors="replace")
            data = json.loads(raw)
            detail = data.get("error", {})
            if isinstance(detail, dict):
                detail = detail.get("message", "")
            text = str(detail or raw)
        except (OSError, ValueError, json.JSONDecodeError):
            text = "上游服务拒绝了请求。"
        text = text.replace(self.api_key, "[redacted]").strip()
        return text[:300]
