from career.ai.base import AIProvider
from career.ai.keys import get_key
from career.config.settings import AISettings

PROVIDERS = ("claude", "gemini", "openai", "local", "none")


def get_provider(settings: AISettings) -> AIProvider | None:
    """The configured provider, or None for rules-only analysis."""
    name = settings.provider
    model = settings.model or None
    if name == "claude":
        from career.ai.claude import ClaudeProvider

        return ClaudeProvider(model, get_key("claude"))
    if name == "openai":
        from career.ai.openai import OpenAIProvider

        return OpenAIProvider(model, get_key("openai"))
    if name == "gemini":
        from career.ai.gemini import GeminiProvider

        return GeminiProvider(model, get_key("gemini"))
    if name == "local":
        from career.ai.local import LocalProvider

        return LocalProvider(model, url=settings.local_url)
    return None
