"""Gemini via the official Google Gen AI SDK (optional dependency: `career-agent[gemini]`)."""

import json
import os
from typing import Any

from career.ai.base import AIError, AIProvider


class GeminiProvider(AIProvider):
    name = "gemini"
    default_model = "gemini-2.5-flash"

    def available(self) -> bool:
        try:
            from google import genai  # noqa: F401
        except ImportError:
            return False
        return bool(self.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))

    def _complete_json(self, system: str, user: str, schema: dict[str, Any], effort: str) -> str:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise AIError("Install the Gemini extra: uv pip install 'career-agent[gemini]'") from exc
        client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
        prompt = f"{user}\n\nRespond with JSON matching this schema:\n{json.dumps(schema)}"
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json"),
            )
        except Exception as exc:  # noqa: BLE001 - the SDK raises several unrelated error types
            raise AIError(f"Gemini API error: {exc}") from exc
        if not response.text:
            raise AIError("Gemini returned no content.")
        return response.text
