from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod


class ProviderError(RuntimeError):
    pass


class ModelProvider(ABC):
    name = "base"

    @property
    def is_mock(self) -> bool:
        return False

    @property
    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str | None:
        raise NotImplementedError


def extract_json(text: str | None) -> dict | None:
    if not text:
        return None

    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, flags=re.S)
    if fenced:
        candidate = fenced.group(1)

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return None

    return parsed if isinstance(parsed, dict) else None

