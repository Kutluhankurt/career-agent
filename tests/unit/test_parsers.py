from career.collector.linux import parse_active_window_id, parse_window_props
from career.collector.macos import parse_front_window, parse_hid_idle


def test_xprop_active_window_id():
    assert parse_active_window_id("_NET_ACTIVE_WINDOW(WINDOW): window id # 0x3a00007\n") == "0x3a00007"
    assert parse_active_window_id("_NET_ACTIVE_WINDOW(WINDOW): window id # 0x0\n") is None
    assert parse_active_window_id("_NET_ACTIVE_WINDOW:  not found.\n") is None


def test_xprop_window_props():
    out = (
        '_NET_WM_NAME(UTF8_STRING) = "temperature_test.py — supervisor — Visual Studio Code"\n'
        'WM_NAME(STRING) = "temperature_test.py"\n'
        'WM_CLASS(STRING) = "code", "Code"\n'
        "_NET_WM_PID(CARDINAL) = 4242\n"
    )
    props = parse_window_props(out)
    assert props["_NET_WM_NAME"] == ["temperature_test.py — supervisor — Visual Studio Code"]
    assert props["WM_CLASS"] == ["code", "Code"]
    assert props["_NET_WM_PID"] == "4242"


def test_xprop_escaped_quotes():
    props = parse_window_props('_NET_WM_NAME(UTF8_STRING) = "say \\"hi\\" \\\\ there"\n')
    assert props["_NET_WM_NAME"] == ['say "hi" \\ there']


def test_xprop_missing_props_ignored():
    props = parse_window_props("_NET_WM_PID:  not found.\n")
    assert props == {}


def test_macos_front_window():
    w = parse_front_window("Code\n812\ntemperature_test.py — supervisor\n")
    assert (w.application, w.pid, w.title) == ("Code", 812, "temperature_test.py — supervisor")
    w = parse_front_window("Finder\n300\n\n")
    assert w.title is None
    assert parse_front_window("") is None


def test_macos_hid_idle():
    out = '    | |   "HIDIdleTime" = 12500000000\n'
    assert parse_hid_idle(out) == 12.5
    assert parse_hid_idle("nothing") is None
