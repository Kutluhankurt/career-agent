"""Collector factory: picks the implementation for the current OS."""

import platform

from career.collector.base import ActiveWindow, ActivityCollector, CollectorUnavailable
from career.collector.mock import MockCollector, Sample


def platform_name() -> str:
    return {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}.get(platform.system(), platform.system())


def get_collector() -> ActivityCollector:
    system = platform.system()
    if system == "Linux":
        from career.collector.linux import LinuxCollector

        return LinuxCollector()
    if system == "Windows":
        from career.collector.windows import WindowsCollector

        return WindowsCollector()
    if system == "Darwin":
        from career.collector.macos import MacOSCollector

        return MacOSCollector()
    raise CollectorUnavailable(f"Unsupported platform: {system}")


__all__ = [
    "ActiveWindow",
    "ActivityCollector",
    "CollectorUnavailable",
    "MockCollector",
    "Sample",
    "get_collector",
    "platform_name",
]
