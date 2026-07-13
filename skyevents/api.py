"""HTTP API.

Requests are served from the SQLite cache only; generation happens in
the background. Responses carry an explicit `coverage` range — the part
of the requested window actually backed by generated years — so that an
empty window outside those years does not look like "no events".
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response

from skyevents import store, texts
from skyevents.generators import GENERATOR_VERSION, generate_year
from skyevents.model import Event, EventType

MAX_WINDOW_DAYS = 400
REFRESH_INTERVAL_S = 6 * 3600

logger = logging.getLogger("skyevents")


def needed_years(today: date) -> list[int]:
    """Current year; plus the next one starting in December"""

    years = [today.year]
    if today.month == 12:
        years.append(today.year + 1)
    return years


def generate_missing():
    """Generate and cache the needed years not yet in the cache.

    A version bump makes previously cached years "missing" again, so
    changing generator logic regenerates the cache on next startup.
    """

    conn = store.connect()
    try:
        cached = set(store.cached_years(conn, GENERATOR_VERSION))
        for year in needed_years(datetime.now(timezone.utc).date()):
            if year in cached:
                continue
            logger.info("generating %d...", year)
            events = generate_year(year)
            store.replace_year(conn, year, GENERATOR_VERSION, events)
            logger.info("cached %d: %d events", year, len(events))
    finally:
        conn.close()


async def refresh_loop():
    """Fill the cache in the background, forever.

    Runs off the event loop thread: pairwise close-approach searches
    can take minutes on the full ephemeris, and /health must answer
    right after startup.
    """

    while True:
        try:
            await asyncio.to_thread(generate_missing)
        except Exception:
            logger.exception("cache generation failed")
        await asyncio.sleep(REFRESH_INTERVAL_S)


@asynccontextmanager
async def lifespan(app):
    task = None
    if os.environ.get("SKYEVENTS_AUTOGEN", "1") != "0":
        task = asyncio.create_task(refresh_loop())
    yield
    if task is not None:
        task.cancel()


app = FastAPI(title="skyevents", version="1.0", lifespan=lifespan)


def coverage_runs(years: list[int]):
    """Contiguous cached-year runs as [start, end) UTC instants"""

    runs = []
    for year in sorted(years):
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        if runs and runs[-1][1] == start:
            runs[-1] = (runs[-1][0], end)
        else:
            runs.append((start, end))
    return runs


def serialize(event: Event, lang: str) -> dict:
    summary, description = texts.render(event, lang)
    return {
        "uid": event.uid,
        "type": event.type,
        "dt_utc": event.dt_utc.isoformat(),
        "bodies": event.bodies,
        "params": event.params,
        "summary": summary,
        "description": description,
        # links to in-the-sky.org left with the feed; a page of our
        # own may fill this in the future
        "url": "",
    }


@app.get("/health")
def health():
    """Liveness for compose healthchecks and CI smoke tests.

    Answers right after startup: an empty cache is reported, not
    awaited (background generation can take minutes on first run).
    """

    conn = store.connect()
    try:
        years = store.cached_years(conn, GENERATOR_VERSION)
    finally:
        conn.close()
    return {"status": "ok",
            "generator_version": GENERATOR_VERSION,
            "years": years}


def ics_escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\r\n", "\n")
            .replace("\r", "\n").replace("\n", "\\n"))


def ics_fold(line: str) -> list[str]:
    """RFC 5545 3.1 folding: content lines of at most 75 octets"""

    out = []
    octets = line.encode("utf-8")
    while len(octets) > 75:
        cut = 75
        while octets[cut] & 0xC0 == 0x80:  # don't split a UTF-8 char
            cut -= 1
        out.append(octets[:cut].decode("utf-8"))
        octets = b" " + octets[cut:]
    out.append(octets.decode("utf-8"))
    return out


@app.get("/v1/calendar.ics")
def calendar_ics(year: int, lang: Literal["en", "ru"] = "en"):
    """Yearly iCal, format-compatible with the in-the-sky.org feed.

    Lets the bot switch data sources by swapping the feed URL before
    it grows a real API client.
    """

    conn = store.connect()
    try:
        if year not in store.cached_years(conn, GENERATOR_VERSION):
            raise HTTPException(
                503, f"year {year} is not generated yet",
                headers={"Retry-After": "600"})
        found = store.events_between(
            conn,
            datetime(year, 1, 1, tzinfo=timezone.utc),
            datetime(year + 1, 1, 1, tzinfo=timezone.utc))
    finally:
        conn.close()

    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//skyevents//EN"]
    for event in found:
        summary, description = texts.render(event, lang)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{event.uid}",
            f"DTSTAMP:{now}",
            f"DTSTART:{event.dt_utc.strftime('%Y%m%dT%H%M%SZ')}",
            f"SUMMARY:{ics_escape(summary)}",
        ]
        if description:
            lines.append(f"DESCRIPTION:{ics_escape(description)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    folded = [part for line in lines for part in ics_fold(line)]
    return Response("\r\n".join(folded) + "\r\n",
                    media_type="text/calendar; charset=utf-8")


@app.get("/v1/events")
def events(
    from_: date = Query(alias="from"),
    to: date = Query(),
    types: str | None = None,
    lang: Literal["en", "ru"] = "en",
):
    """Events with from <= dt_utc < to (dates are UTC midnights)"""

    if from_ > to:
        raise HTTPException(422, "'from' must not be after 'to'")
    if (to - from_).days > MAX_WINDOW_DAYS:
        raise HTTPException(
            422, f"window wider than {MAX_WINDOW_DAYS} days")
    type_filter = None
    if types is not None:
        try:
            type_filter = [EventType(t) for t in types.split(",")]
        except ValueError:
            raise HTTPException(422, f"unknown event type in {types!r}")

    start = datetime.combine(from_, time.min, tzinfo=timezone.utc)
    end = datetime.combine(to, time.min, tzinfo=timezone.utc)

    conn = store.connect()
    try:
        years = store.cached_years(conn, GENERATOR_VERSION)
        run = next((r for r in coverage_runs(years)
                    if r[0] < end and start < r[1]), None)
        if run is None:
            return {"events": [], "coverage": None}
        covered_start = max(start, run[0])
        covered_end = min(end, run[1])
        found = store.events_between(
            conn, covered_start, covered_end, type_filter)
    finally:
        conn.close()

    return {
        "events": [serialize(e, lang) for e in found],
        "coverage": {"from": covered_start.isoformat(),
                     "to": covered_end.isoformat()},
    }
