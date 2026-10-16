"""OpenAI via the official SDK (optional dependency: `career-agent[openai]`)."""

import os
from typing import Any

from career.ai.base import AIError, AIProvider


class OpenAIProvider(AIProvider):
    name = "openai"
    default_model = "gpt-5"

    def available(self) -> bool:
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return bool(self.api_key or os.environ.get("OPENAI_API_KEY"))

    def _complete_json(self, system: str, user: str, schema: dict[str, Any], effort: str) -> str:
        try:
            import openai
        except ImportError as exc:
            raise AIError("Install the OpenAI extra: uv pip install 'career-agent[openai]'") from exc
        client = openai.OpenAI(api_key=self.api_key) if self.api_key else openai.OpenAI()
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_schema", "json_schema": {"name": "result", "schema": schema, "strict": True}},
            )
        except openai.AuthenticationError as exc:
            raise AIError("OpenAI rejected the API key. Set it again with `career config ai`.") from exc
        except openai.APIError as exc:
            raise AIError(f"OpenAI API error: {exc}") from exc
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise AIError("OpenAI declined to analyze this session.")
        if not message.content:
            raise AIError("OpenAI returned no content.")
        return message.content
