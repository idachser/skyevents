from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from skyevents import store
from skyevents.api import app
from skyevents.generators import GENERATOR_VERSION
from skyevents.model import Event, EventType

client = TestClient(app)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """Empty cache in a temp dir, wired via SKYEVENTS_CACHE"""

    path = str(tmp_path / "cache.db")
    monkeypatch.setenv("SKYEVENTS_CACHE", path)
    conn = store.connect(path)
    yield conn
    conn.close()


def seed_2026(conn, version=GENERATOR_VERSION):
    events = [
        Event.create(
            EventType.MOON_PHASE,
            datetime(2026, 1, 3, 10, 2, tzinfo=timezone.utc),
            ["moon"], {"phase": "full"}),
        Event.create(
            EventType.CLOSE_APPROACH,
            datetime(2026, 5, 19, 2, 3, tzinfo=timezone.utc),
            ["moon", "venus"],
            {"separation_deg": 2.94, "sun_elongation_deg": 32.0}),
    ]
    store.replace_year(conn, 2026, version, events)
    return events


def test_health_with_empty_cache(cache):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["years"] == []


def test_health_reports_cached_years(cache):
    seed_2026(cache)
    assert client.get("/health").json()["years"] == [2026]


def test_events_in_window(cache):
    seed_2026(cache)
    resp = client.get(
        "/v1/events", params={"from": "2026-01-01", "to": "2026-02-01"})
    assert resp.status_code == 200
    data = resp.json()
    assert [e["uid"] for e in data["events"]] == [
        "moon_phase:moon:20260103"]
    event = data["events"][0]
    assert event["summary"] == "Full Moon"
    assert event["url"] == ""
    assert event["dt_utc"] == "2026-01-03T10:02:00+00:00"
    assert data["coverage"] == {"from": "2026-01-01T00:00:00+00:00",
                                "to": "2026-02-01T00:00:00+00:00"}


def test_lang_ru(cache):
    seed_2026(cache)
    resp = client.get("/v1/events", params={
        "from": "2026-05-01", "to": "2026-06-01", "lang": "ru"})
    assert resp.json()["events"][0]["summary"] == "Сближение Луны и Венеры"


def test_types_filter(cache):
    seed_2026(cache)
    resp = client.get("/v1/events", params={
        "from": "2026-01-01", "to": "2026-12-31",
        "types": "close_approach"})
    assert [e["type"] for e in resp.json()["events"]] == ["close_approach"]


def test_window_outside_coverage_is_not_no_events(cache):
    seed_2026(cache)
    resp = client.get(
        "/v1/events", params={"from": "2030-01-01", "to": "2030-02-01"})
    assert resp.status_code == 200
    assert resp.json() == {"events": [], "coverage": None}


def test_partially_covered_window_is_clipped(cache):
    seed_2026(cache)
    resp = client.get(
        "/v1/events", params={"from": "2026-12-01", "to": "2027-02-01"})
    data = resp.json()
    assert data["coverage"] == {"from": "2026-12-01T00:00:00+00:00",
                                "to": "2027-01-01T00:00:00+00:00"}


def test_stale_generator_version_is_not_coverage(cache):
    seed_2026(cache, version=GENERATOR_VERSION - 1)
    resp = client.get(
        "/v1/events", params={"from": "2026-01-01", "to": "2026-02-01"})
    assert resp.json() == {"events": [], "coverage": None}


@pytest.mark.parametrize("params", [
    {"from": "2026-02-01", "to": "2026-01-01"},
    {"from": "2026-01-01", "to": "2027-06-01"},
    {"from": "2026-01-01", "to": "2026-02-01", "types": "nope"},
    {"from": "2026-01-01", "to": "2026-02-01", "lang": "de"},
    {"from": "2026-01-01"},
])
def test_validation_rejected(cache, params):
    seed_2026(cache)
    assert client.get("/v1/events", params=params).status_code == 422
