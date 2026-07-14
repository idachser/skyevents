from datetime import datetime, timezone

from skyevents import store
from skyevents.model import Event, EventType


def make_event(day: int, type=EventType.MOON_PHASE, params=None):
    return Event.create(
        type, datetime(2026, 1, day, 12, 30, tzinfo=timezone.utc),
        ["moon"], params or {"phase": "full"})


def test_init_enables_wal(tmp_path):
    conn = store.init(str(tmp_path / "cache.db"))
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_writer_commits_while_a_reader_is_inside_a_transaction(tmp_path):
    """Discriminates WAL from rollback journal: there the writer's
    commit needs an exclusive lock and stalls on the open reader."""

    path = str(tmp_path / "cache.db")
    writer = store.init(path)
    reader = store.connect(path)
    store.replace_year(writer, 2026, 1, [make_event(3)])

    reader.execute("BEGIN")
    assert reader.execute("SELECT count(*) FROM events").fetchone()[0] == 1
    writer.execute("PRAGMA busy_timeout=500")  # fail fast, not in 15 s
    store.replace_year(writer, 2027, 1, [make_event(5)])
    reader.rollback()
    assert store.cached_years(writer, 1) == [2026, 2027]


def test_round_trip(tmp_path):
    conn = store.init(str(tmp_path / "cache.db"))
    events = [make_event(3), make_event(10)]
    store.replace_year(conn, 2026, 1, events)

    got = store.events_between(
        conn,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert got == events
    assert store.cached_years(conn, 1) == [2026]


def test_range_is_half_open_and_ordered(tmp_path):
    conn = store.init(str(tmp_path / "cache.db"))
    store.replace_year(conn, 2026, 1, [make_event(10), make_event(3)])

    got = store.events_between(
        conn,
        datetime(2026, 1, 3, 12, 30, tzinfo=timezone.utc),
        datetime(2026, 1, 10, 12, 30, tzinfo=timezone.utc))
    assert [e.dt_utc.day for e in got] == [3]


def test_type_filter(tmp_path):
    conn = store.init(str(tmp_path / "cache.db"))
    store.replace_year(conn, 2026, 1, [
        make_event(3),
        make_event(5, EventType.LUNAR_APSIS,
                   {"kind": "perigee", "distance_km": 360000.0}),
    ])

    got = store.events_between(
        conn,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2027, 1, 1, tzinfo=timezone.utc),
        types=[EventType.LUNAR_APSIS])
    assert [e.type for e in got] == [EventType.LUNAR_APSIS]


def test_replace_year_drops_stale_events(tmp_path):
    conn = store.init(str(tmp_path / "cache.db"))
    store.replace_year(conn, 2026, 1, [make_event(3), make_event(10)])
    store.replace_year(conn, 2026, 2, [make_event(10)])

    got = store.events_between(
        conn,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert [e.dt_utc.day for e in got] == [10]
    assert store.cached_years(conn, 1) == []
    assert store.cached_years(conn, 2) == [2026]
