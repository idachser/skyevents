from skyevents import ephemeris


def test_data_dir_default(monkeypatch):
    monkeypatch.delenv("SKYEVENTS_DATA", raising=False)
    assert ephemeris.data_dir() == "data"


def test_data_dir_from_env(monkeypatch):
    monkeypatch.setenv("SKYEVENTS_DATA", "/var/lib/skyevents")
    assert ephemeris.data_dir() == "/var/lib/skyevents"
