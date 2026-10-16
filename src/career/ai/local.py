"""Local models through Ollama (http://127.0.0.1:11434). Nothing leaves the computer."""

import json
from typing import Any

import httpx

from career.ai.base import AIError, AIProvider


class LocalProvider(AIProvider):
    name = "local"
    default_model = "llama3.1"

    def __init__(self, model: str | None = None, api_key: str | None = None, url: str = "http://127.0.0.1:11434"):
        super().__init__(model, api_key)
        self.url = url.rstrip("/")

    def available(self) -> bool:
        try:
            tags = httpx.get(f"{self.url}/api/tags", timeout=1.5).json()
        except (httpx.HTTPError, ValueError):
            return False
        names = {m.get("name", "").split(":")[0] for m in tags.get("models", [])}
        return self.model.split(":")[0] in names

    def _complete_json(self, system: str, user: str, schema: dict[str, Any], effort: str) -> str:
        try:
            response = httpx.post(
                f"{self.url}/api/chat",
                json={"model": self.model, "stream": False, "format": schema, "options": {"temperature": 0},
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                timeout=180,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIError(f"Local model unavailable at {self.url}: {exc}") from exc
        try:
            return response.json()["message"]["content"]
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise AIError("Local model returned an unexpected response.") from exc
