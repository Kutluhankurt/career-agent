"""Claude via the official Anthropic SDK (optional dependency: `career-agent[claude]`)."""

import logging
from pathlib import Path
from typing import Any

from career.ai.base import AIError, AIProvider

log = logging.getLogger(__name__)

# Server-side fallback: if the model declines a request, the API re-runs it on a
# suitable fallback model inside the same call.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeProvider(AIProvider):
    name = "claude"
    default_model = "claude-opus-5-5"

    def available(self) -> bool:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        import os

        return bool(self.api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                    or (Path.home() / ".config" / "anthropic").exists())

    def _client(self):
        import anthropic

        return anthropic.Anthropic(api_key=self.api_key) if self.api_key else anthropic.Anthropic()

    def _complete_json(self, system: str, user: str, schema: dict[str, Any], effort: str) -> str:
        try:
            import anthropic
        except ImportError as exc:
            raise AIError("Install the Claude extra: uv pip install 'career-agent[claude]'") from exc
        try:
            response = self._client().beta.messages.create(
                model=self.model,
                max_tokens=4000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
                betas=[_FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as exc:
            raise AIError("Claude rejected the API key. Set it again with `career config ai`.") from exc
        except anthropic.RateLimitError as exc:
            raise AIError("Claude rate limit reached; analysis will retry later.") from exc
        except anthropic.APIStatusError as exc:
            raise AIError(f"Claude API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise AIError("Can't reach the Claude API (offline?).") from exc
        if response.stop_reason == "refusal":
            raise AIError("Claude declined to analyze this session.")
        if response.stop_reason == "max_tokens":
            raise AIError("Claude's answer was cut off.")
        text = "".join(block.text for block in response.content if block.type == "text")
        if not text:
            raise AIError("Claude returned no text.")
        return text
