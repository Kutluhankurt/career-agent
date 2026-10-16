from career.config.settings import Settings, load_settings, save_settings


def test_missing_file_gives_defaults(tmp_path):
    s = load_settings(tmp_path / "nope.toml")
    assert s.collector.interval == 5.0
    assert s.server.port == 7342
    assert s.privacy.screen_understanding is False


def test_roundtrip(tmp_path):
    path = tmp_path / "config.toml"
    s = Settings()
    s.collector.idle_threshold = 120
    s.ai.provider = "gemini"
    save_settings(s, path)
    loaded = load_settings(path)
    assert loaded.collector.idle_threshold == 120
    assert loaded.ai.provider == "gemini"


def test_partial_file_fills_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[collector]\ninterval = 2\n')
    s = load_settings(path)
    assert s.collector.interval == 2
    assert s.collector.idle_threshold == 300
    assert s.general.timezone == "Europe/Istanbul"
