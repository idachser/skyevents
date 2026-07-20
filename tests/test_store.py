import os
import sqlite3
from datetime import datetime, timezone

import pytest

from skyevents import store
from skyevents.model import Event, EventType

YEAR_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
YEAR_END = datetime(2027, 1, 1, tzinfo=timezone.utc)


def make_event(day: int, type=EventType.MOON_PHASE, params=None):
    return Event.create(
        type, datetime(2026, 1, day, 12, 30, tzinfo=timezone.utc),
        ["moon"], params or {"phase": "full"})


@pytest.fixture
def cache_path(tmp_path):
    path = str(tmp_path / "cache.db")
    store.init(path)
    return path


@pytest.fixture
def conn(cache_path):
    connection = store.connect(cache_path)
    yield connection
    connection.close()


def test_init_enables_wal(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_init_rebuilds_a_deleted_cache(cache_path):
    """Ops deleting cache.db must not need a service restart."""

    os.remove(cache_path)
    store.init(cache_path)
    conn = store.connect(cache_path)
    assert store.cached_years(conn, 1) == []
    store.replace_year(conn, 2026, 1, [make_event(3)])
    assert store.cached_years(conn, 1) == [2026]
    conn.close()


def test_reader_keeps_its_snapshot_while_a_writer_commits(cache_path):
    """Discriminates WAL from rollback journal: there the writer's
    commit needs an exclusive lock and stalls on the open reader."""

    writer = store.connect(cache_path)
    reader = store.connect(cache_path)
    store.replace_year(writer, 2026, 1, [make_event(3)])

    reader.execute("BEGIN")
    before = store.events_between(reader, YEAR_START, YEAR_END)
    writer.execute("PRAGMA busy_timeout=500")  # fail fast, not in 15 s
    store.replace_year(writer, 2026, 1, [make_event(3), make_event(10)])
    # the reader's transaction still sees the pre-write snapshot
    assert store.events_between(reader, YEAR_START, YEAR_END) == before
    reader.rollback()
    assert [e.dt_utc.day
            for e in store.events_between(reader, YEAR_START, YEAR_END)
            ] == [3, 10]


def test_round_trip(conn):
    events = [make_event(3), make_event(10)]
    store.replace_year(conn, 2026, 1, events)

    assert store.events_between(conn, YEAR_START, YEAR_END) == events
    assert store.cached_years(conn, 1) == [2026]


def test_range_is_half_open_and_ordered(conn):
    store.replace_year(conn, 2026, 1, [make_event(10), make_event(3)])

    got = store.events_between(
        conn,
        datetime(2026, 1, 3, 12, 30, tzinfo=timezone.utc),
        datetime(2026, 1, 10, 12, 30, tzinfo=timezone.utc))
    assert [e.dt_utc.day for e in got] == [3]


def test_type_filter(conn):
    store.replace_year(conn, 2026, 1, [
        make_event(3),
        make_event(5, EventType.LUNAR_APSIS,
                   {"kind": "perigee", "distance_km": 360000.0}),
    ])

    got = store.events_between(conn, YEAR_START, YEAR_END,
                               types=[EventType.LUNAR_APSIS])
    assert [e.type for e in got] == [EventType.LUNAR_APSIS]


def test_replace_year_drops_stale_events(conn):
    store.replace_year(conn, 2026, 1, [make_event(3), make_event(10)])
    store.replace_year(conn, 2026, 2, [make_event(10)])

    got = store.events_between(conn, YEAR_START, YEAR_END)
    assert [e.dt_utc.day for e in got] == [10]
    assert store.cached_years(conn, 1) == []
    assert store.cached_years(conn, 2) == [2026]


def test_corrupt_cache_raises_database_error(tmp_path):
    """The class api.lifespan and /health must catch."""

    path = str(tmp_path / "cache.db")
    with open(path, "w") as f:
        f.write("this is not a sqlite database " * 30)
    with pytest.raises(sqlite3.DatabaseError):
        store.init(path)
