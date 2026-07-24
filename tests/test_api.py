from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from skyevents import api, store
from skyevents.api import app
from skyevents.generators import GENERATOR_VERSION
from skyevents.model import Event, EventType

client = TestClient(app)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """Empty cache in a temp dir, wired via SKYEVENTS_CACHE"""

    path = str(tmp_path / "cache.db")
    monkeypatch.setenv("SKYEVENTS_CACHE", path)
    store.init(path)
    conn = store.connect(path)
    yield conn
    conn.close()


def frozen_datetime(instant):
    """Stand-in for api.datetime with now() pinned to `instant`.

    A subclass so the plain datetime(...) calls in api.py keep working.
    Rejects a tz-less now(): "current year" must be the UTC one, and a
    naive now() would silently be the server's local year -- wrong on
    either side of midnight UTC for most deployments.
    """

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is timezone.utc, "api must ask for UTC explicitly"
            return instant

    return Frozen


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


def test_needed_years_regular_month():
    from skyevents.api import needed_years
    assert needed_years(datetime(2026, 7, 10).date()) == [2026]


def test_needed_years_december_includes_next():
    from skyevents.api import needed_years
    assert needed_years(datetime(2026, 12, 1).date()) == [2026, 2027]


def test_generate_missing_fills_cache(cache):
    from skyevents.api import generate_missing
    generate_missing()
    years = store.cached_years(cache, GENERATOR_VERSION)
    assert datetime.now(timezone.utc).year in years
    # a second run is a no-op (already cached)
    generate_missing()
    assert store.cached_years(cache, GENERATOR_VERSION) == years


def test_generate_missing_regenerates_a_stale_year(cache):
    """An aged record is rebuilt so newly-added comets reach the year.

    The year is present and at the current version, but its record is
    older than MAX_CACHE_AGE, so generate_missing must recompute it
    rather than skip it as already cached.
    """

    from datetime import timedelta

    from skyevents.api import generate_missing

    year = datetime.now(timezone.utc).year
    marker = Event.create(
        EventType.MOON_PHASE,
        datetime(year, 1, 1, 0, 0, tzinfo=timezone.utc),
        ["moon"], {"phase": "new"})
    store.replace_year(cache, year, GENERATOR_VERSION, [marker])
    stale = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    with cache:
        cache.execute("UPDATE years SET generated_at = ? WHERE year = ?",
                      (stale, year))

    generate_missing()

    ages = store.year_ages(cache, GENERATOR_VERSION)
    assert datetime.fromisoformat(stale) < ages[year], "record not refreshed"
    uids = [e.uid for e in store.events_between(
        cache,
        datetime(year, 1, 1, tzinfo=timezone.utc),
        datetime(year + 1, 1, 1, tzinfo=timezone.utc))]
    assert marker.uid not in uids, "stale placeholder survived regeneration"
    assert len(uids) > 1


def test_health_with_empty_cache(cache):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["years"] == []


def test_health_reports_cached_years(cache):
    seed_2026(cache)
    assert client.get("/health").json()["years"] == [2026]


def test_health_is_503_when_the_cache_is_unusable(tmp_path, monkeypatch):
    """A corrupt cache must fail the healthcheck, not 500 per request."""

    path = str(tmp_path / "cache.db")
    with open(path, "w") as f:
        f.write("this is not a sqlite database " * 30)
    monkeypatch.setenv("SKYEVENTS_CACHE", path)

    resp = client.get("/health")
    assert resp.status_code == 503
    assert "unusable" in resp.json()["detail"]


def test_startup_survives_a_corrupt_cache(tmp_path, monkeypatch):
    """lifespan logs and continues so /health can report the problem."""

    path = str(tmp_path / "cache.db")
    with open(path, "w") as f:
        f.write("this is not a sqlite database " * 30)
    monkeypatch.setenv("SKYEVENTS_CACHE", path)
    monkeypatch.setenv("SKYEVENTS_AUTOGEN", "0")

    with TestClient(app) as started:  # runs lifespan
        assert started.get("/health").status_code == 503


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


def test_calendar_ics(cache):
    seed_2026(cache)
    resp = client.get("/v1/calendar.ics", params={"year": 2026})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/calendar")
    text = resp.text
    assert text.startswith("BEGIN:VCALENDAR\r\n")
    assert "UID:moon_phase:moon:20260103" in text
    assert "DTSTART:20260103T100200Z" in text
    assert "SUMMARY:Full Moon" in text
    assert text.count("BEGIN:VEVENT") == 2


def test_ics_escape_normalizes_cr():
    from skyevents.api import ics_escape
    assert ics_escape("a\r\nb\rc") == "a\\nb\\nc"


def test_ics_fold_75_octets():
    from skyevents.api import ics_fold

    assert ics_fold("short") == ["short"]

    line = "SUMMARY:" + "я" * 100  # 2-octet characters
    folded = ics_fold(line)
    assert all(len(part.encode()) <= 75 for part in folded)
    assert all(part.startswith(" ") for part in folded[1:])
    # unfolding restores the original line
    assert folded[0] + "".join(p[1:] for p in folded[1:]) == line


def test_calendar_ics_folds_long_lines(cache):
    long_name = ("Southern Delta Aquariids Extended Observation "
                 "Campaign of the Whole Summer")
    store.replace_year(cache, 2026, GENERATOR_VERSION, [Event.create(
        EventType.METEOR_SHOWER,
        datetime(2026, 7, 30, 12, tzinfo=timezone.utc),
        ["sda-extended"], {"name": long_name, "zhr": 25})])
    resp = client.get("/v1/calendar.ics", params={"year": 2026})
    lines = resp.text.split("\r\n")
    assert any(line.startswith(" ") for line in lines)  # folded
    for line in lines:
        assert len(line.encode()) <= 75
    unfolded = resp.text.replace("\r\n ", "")
    assert f"SUMMARY:{long_name} meteor shower" in unfolded


def test_calendar_ics_ungenerated_year_is_503(cache):
    seed_2026(cache)
    resp = client.get("/v1/calendar.ics", params={"year": 2030})
    assert resp.status_code == 503
    assert resp.headers["retry-after"]


def test_calendar_ics_year_defaults_to_now(cache, monkeypatch):
    """A bare feed URL must keep working when the year rolls over."""

    seed_2026(cache)
    monkeypatch.setattr(
        api, "datetime",
        frozen_datetime(datetime(2026, 7, 20, tzinfo=timezone.utc)))
    resp = client.get("/v1/calendar.ics")
    assert resp.status_code == 200
    assert "UID:moon_phase:moon:20260103" in resp.text


@pytest.mark.parametrize("params", [
    {"from": "2026-02-01", "to": "2026-01-01"},
    {"from": "2026-01-01", "to": "2027-06-01"},
    {"from": "2026-01-01", "to": "2026-02-01", "types": "nope"},
    {"from": "2026-01-01", "to": "2026-02-01", "lang": "de"},
    {"from": "2026-01-01"},
    # a misspelled filter must fail loudly, not silently return everything
    {"from": "2026-01-01", "to": "2026-02-01", "type": "moon_phase"},
    {"from": "2026-01-01", "to": "2026-02-01", "limit": "10"},
])
def test_validation_rejected(cache, params):
    seed_2026(cache)
    assert client.get("/v1/events", params=params).status_code == 422


@pytest.mark.parametrize("params", [
    {"year": 2026, "langs": "ru"},
    {"years": 2026},
])
def test_calendar_ics_rejects_unknown_params(cache, params):
    seed_2026(cache)
    assert client.get(
        "/v1/calendar.ics", params=params).status_code == 422


@pytest.mark.parametrize("types", [
    "moon_phase, close_approach",     # space after the comma
    "moon_phase,close_approach,",     # trailing comma
    " moon_phase , close_approach ",  # both, everywhere
])
def test_types_tolerates_formatting_slack(cache, types):
    seed_2026(cache)
    resp = client.get("/v1/events", params={
        "from": "2026-01-01", "to": "2026-12-01", "types": types})
    assert resp.status_code == 200
    assert {e["type"] for e in resp.json()["events"]} == {
        "moon_phase", "close_approach"}


@pytest.mark.parametrize("types", ["", " ", ",", " , "])
def test_types_naming_nothing_is_422(cache, types):
    """An empty filter would mean "no events", not "no filter"."""

    seed_2026(cache)
    resp = client.get("/v1/events", params={
        "from": "2026-01-01", "to": "2026-12-01", "types": types})
    assert resp.status_code == 422


@pytest.mark.parametrize("query", [
    # a repeated param must not silently collapse to the last value;
    # requests/httpx serialize params={"types": [...]} exactly this way
    "from=2026-01-01&to=2026-02-01&types=moon_phase&types=close_approach",
    "from=2026-01-01&from=2026-06-01&to=2026-07-01",
    "from=2026-01-01&to=2026-02-01&lang=en&lang=ru",
])
def test_repeated_query_param_rejected(cache, query):
    seed_2026(cache)
    assert client.get(f"/v1/events?{query}").status_code == 422


def test_repeated_query_param_rejected_on_ics(cache):
    seed_2026(cache)
    assert client.get(
        "/v1/calendar.ics?year=2026&year=2027").status_code == 422


def test_health_rejects_unknown_params(cache):
    assert client.get("/health", params={"foo": "1"}).status_code == 422


@pytest.mark.parametrize("year", [0, 1899, 2101, 999999999999])
def test_calendar_ics_year_out_of_range_is_422(cache, year):
    """422 rather than a 500 from datetime(year, 1, 1) overflowing."""

    seed_2026(cache)
    assert client.get(
        "/v1/calendar.ics", params={"year": year}).status_code == 422
