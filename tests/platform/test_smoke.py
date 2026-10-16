"""Smoke tests against the real desktop. Run on each OS with: pytest -m platform"""

import pytest

from career.collector import get_collector
from career.events.processor import EventProcessor

pytestmark = pytest.mark.platform


@pytest.fixture
def collector():
    c = get_collector()
    c.start()
    yield c
    c.stop()


def test_active_window(collector):
    window = collector.get_active_window()
    print("active window:", window)
    assert window is None or window.application or window.title


def test_idle_time(collector):
    idle = collector.get_idle_time()
    print("idle seconds:", idle)
    assert idle is None or idle >= 0


def test_running_apps(collector):
    assert len(collector.get_running_apps()) > 0


def test_processor_emits_focus(collector):
    events = EventProcessor(collector, idle_threshold=10**9).tick()
    print("events:", events)
    if collector.get_active_window() is not None:
        assert events and events[0].type == "window_focus"
