"""Provider-independent LLM interface plus a deterministic mock and an OpenAI-compatible client."""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..config import Settings
from . import prompts


class ProviderError(Exception):
    pass


class LLMProvider(ABC):
    name = "base"
    is_mock = False

    @abstractmethod
    def complete_json(self, system: str, user: str) -> dict: ...

    def interpret_action(self, text: str, candidates: dict) -> dict:
        user = f"Candidates: {json.dumps(candidates)}\n<player_input>{text}</player_input>"
        return self.complete_json(prompts.INTERPRETER_SYSTEM, user)

    def narrate(self, context: dict) -> dict:
        return self.complete_json(prompts.GM_SYSTEM, "Context: " + json.dumps(context))

    def generate_world_stage(self, stage: str, context: dict) -> dict:
        return self.complete_json(prompts.WORLD_SYSTEM, f"Stage: {stage}\nContext: {json.dumps(context)}")


class OpenAICompatibleProvider(LLMProvider):
    name = "openai-compatible"

    def __init__(self, api_key: str, base_url: str, model: str, client: httpx.Client | None = None, timeout: float = 30.0):
        self.api_key, self.base_url, self.model = api_key, base_url.rstrip("/"), model
        self.client = client or httpx.Client(timeout=timeout)

    def complete_json(self, system: str, user: str) -> dict:
        try:
            r = self.client.post(f"{self.base_url}/chat/completions",
                                 headers={"Authorization": f"Bearer {self.api_key}"},
                                 json={"model": self.model, "temperature": 0.7, "response_format": {"type": "json_object"},
                                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise ProviderError(f"LLM request failed: {e}") from e
        return parse_json_loose(content)


def parse_json_loose(text: str) -> dict:
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        data = json.loads(t)
    except json.JSONDecodeError as e:
        raise ProviderError("Model returned malformed JSON") from e
    if not isinstance(data, dict):
        raise ProviderError("Model returned non-object JSON")
    return data


def get_provider(settings: Settings) -> LLMProvider:
    if settings.llm_api_key:
        return OpenAICompatibleProvider(settings.llm_api_key, settings.llm_base_url, settings.llm_model)
    from .mock_provider import MockProvider
    return MockProvider()
