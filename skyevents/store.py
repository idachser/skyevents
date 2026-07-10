"""SQLite cache of generated events, keyed by year.

The generator version lives here, not in uids: bumping it makes the
service regenerate years while uids stay determined by the event
identity alone (otherwise every logic update would change all uids and
breed duplicates in the bot's upsert table).
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

from skyevents.ephemeris import data_dir
from skyevents.model import Event

SCHEMA = """
CREATE TABLE IF NOT EXISTS years (
    year INTEGER PRIMARY KEY,
    generator_version INTEGER NOT NULL,
    generated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    uid TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    type TEXT NOT NULL,
    dt_utc TEXT NOT NULL,
    bodies TEXT NOT NULL,
    params TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_dt ON events (dt_utc);
CREATE INDEX IF NOT EXISTS events_year ON events (year);
"""


def db_path() -> str:
    return os.environ.get(
        "SKYEVENTS_CACHE", os.path.join(data_dir(), "cache.db"))


def connect(path: str | None = None) -> sqlite3.Connection:
    path = path or db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def replace_year(conn, year: int, version: int, events: list[Event]):
    with conn:
        conn.execute("DELETE FROM events WHERE year = ?", (year,))
        conn.executemany(
            "INSERT OR REPLACE INTO events VALUES (?, ?, ?, ?, ?, ?)",
            [(e.uid, year, e.type, e.dt_utc.isoformat(),
              json.dumps(e.bodies), json.dumps(e.params))
             for e in events])
        conn.execute(
            "INSERT OR REPLACE INTO years VALUES (?, ?, ?)",
            (year, version, datetime.now(timezone.utc).isoformat()))


def cached_years(conn, version: int) -> list[int]:
    """Years generated with exactly this version, ascending"""

    rows = conn.execute(
        "SELECT year FROM years WHERE generator_version = ?", (version,))
    return sorted(row[0] for row in rows)


def events_between(conn, start: datetime, end: datetime,
                   types: list[str] | None = None) -> list[Event]:
    """Events with start <= dt_utc < end, ordered by time"""

    query = ("SELECT uid, type, dt_utc, bodies, params FROM events"
             " WHERE dt_utc >= ? AND dt_utc < ?")
    args = [start.isoformat(), end.isoformat()]
    if types:
        query += f" AND type IN ({', '.join('?' * len(types))})"
        args += list(types)
    query += " ORDER BY dt_utc"
    return [
        Event(uid=uid, type=type, dt_utc=datetime.fromisoformat(dt),
              bodies=json.loads(bodies), params=json.loads(params))
        for uid, type, dt, bodies, params in conn.execute(query, args)
    ]
