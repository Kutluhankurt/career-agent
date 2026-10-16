"""API keys live in the OS keychain (macOS Keychain, Windows Credential Manager,
Secret Service on Linux). Never in config files, the database or logs.

An environment variable (e.g. ANTHROPIC_API_KEY) also works and wins over the keychain.
"""

import logging
import os

log = logging.getLogger(__name__)

SERVICE = "career-agent"
ENV_VARS = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}


def get_key(provider: str) -> str | None:
    env = ENV_VARS.get(provider)
    if env and os.environ.get(env):
        return os.environ[env]
    if provider == "gemini" and os.environ.get("GOOGLE_API_KEY"):
        return os.environ["GOOGLE_API_KEY"]
    try:
        import keyring

        return keyring.get_password(SERVICE, provider)
    except Exception as exc:  # noqa: BLE001 - no keychain backend on this machine
        log.debug("Keychain unavailable: %s", exc)
        return None


def set_key(provider: str, key: str) -> None:
    import keyring

    keyring.set_password(SERVICE, provider, key)


def delete_key(provider: str) -> None:
    try:
        import keyring

        keyring.delete_password(SERVICE, provider)
    except Exception:  # noqa: BLE001
        pass


def has_key(provider: str) -> bool:
    return bool(get_key(provider))
