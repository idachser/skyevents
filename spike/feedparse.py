"""Download and parse the in-the-sky.org yearly iCal feed.

The feed is fetched into the gitignored data/ directory and must never
be committed (© Dominic Ford). Only stage-2 event types are extracted;
everything else (comets, asteroids, "well placed", occultations,
retrograde stations, dichotomy…) is ignored.
"""

import os
import re
import urllib.request
from datetime import datetime, timezone

from skyevents.ephemeris import data_dir
from spike.records import KNOWN_BODIES, Rec, canonical

FEED_URL = "https://in-the-sky.org/newscalyear_ical.php?year={year}&maxdiff=7"

SEASONS = {
    "March equinox": "march_equinox",
    "June solstice": "june_solstice",
    "September equinox": "september_equinox",
    "December solstice": "december_solstice",
}

METEOR_RE = re.compile(r"^(.+?) meteor shower")
PAIR_RE = re.compile(r"^(Close approach|Conjunction) of (.+)$")
PLANET_SUN_RE = re.compile(
    r"^(\w+) at (opposition|solar conjunction"
    r"|inferior solar conjunction|superior solar conjunction)$")
ELONGATION_RE = re.compile(r"^(\w+) at greatest elongation (east|west)$")
ECLIPSE_RE = re.compile(
    r"^(Total|Partial|Annular|Hybrid|Penumbral) (solar|lunar) eclipse$")


def fetch(year: int) -> str:
    """Feed text for the year, downloaded once into data/feed/"""

    path = os.path.join(data_dir(), "feed", f"feed_{year}.ics")
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with urllib.request.urlopen(FEED_URL.format(year=year)) as resp:
            body = resp.read()
        with open(path, "wb") as f:
            f.write(body)
    with open(path, encoding="utf-8") as f:
        return f.read()


def parse_bodies(text: str):
    """"the Moon, Saturn and Neptune" -> ("moon", "saturn", "neptune")

    Returns None if any participant is not a body we generate events
    for (stars, clusters like M45, asteroids...).
    """

    text = text.replace(" and ", ", ")
    names = [n.strip().removeprefix("the ").lower()
             for n in text.split(",")]
    if not all(n in KNOWN_BODIES for n in names):
        return None
    return canonical(names)


def classify(summary: str) -> Rec | None:
    s = summary.strip()

    if s == "New Moon":
        return Rec("moon_phase", ("moon",), None, "new")
    if s in ("Full Moon", "Blue Moon"):  # Blue Moon = 13th full moon
        return Rec("moon_phase", ("moon",), None, "full")
    if s == "Moon at First Quarter":
        return Rec("moon_phase", ("moon",), None, "first_quarter")
    if s == "Moon at Last Quarter":
        return Rec("moon_phase", ("moon",), None, "last_quarter")

    if s in SEASONS:
        return Rec("season", ("sun",), None, SEASONS[s])

    if s == "The Moon at apogee":
        return Rec("lunar_apsis", ("moon",), None, "apogee")
    if s == "The Moon at perigee":
        return Rec("lunar_apsis", ("moon",), None, "perigee")

    m = ELONGATION_RE.match(s)
    if m:
        return Rec("elongation", (m.group(1).lower(),), None, m.group(2))

    m = PLANET_SUN_RE.match(s)
    if m and m.group(1).lower() in KNOWN_BODIES:
        kind = {
            "opposition": "opposition",
            "solar conjunction": "conjunction",
            "inferior solar conjunction": "inferior",
            "superior solar conjunction": "superior",
        }[m.group(2)]
        return Rec("planet_sun", (m.group(1).lower(),), None, kind)

    m = PAIR_RE.match(s)
    if m:
        bodies = parse_bodies(m.group(2))
        if bodies is None:
            return None
        type = ("close_approach" if m.group(1) == "Close approach"
                else "ra_conjunction")
        return Rec(type, bodies, None)

    m = ECLIPSE_RE.match(s)
    if m:
        type = f"{m.group(2)}_eclipse"
        bodies = ("sun", "moon") if m.group(2) == "solar" else ("moon",)
        return Rec(type, bodies, None, m.group(1).lower())

    m = METEOR_RE.match(s)
    if m:
        return Rec("meteor_shower", (), None, m.group(1).strip())

    return None


def parse(year: int) -> list[Rec]:
    raw = fetch(year)
    raw = raw.replace("\r\n ", "").replace("\r\n\t", "")  # unfold

    events = []
    for block in raw.split("BEGIN:VEVENT")[1:]:
        dt = re.search(r"^DTSTART:(\d{8}T\d{6})Z$", block, re.M)
        summary = re.search(r"^SUMMARY(?:;LANGUAGE=\w+)?:(.*)$", block, re.M)
        if not dt or not summary:
            continue
        rec = classify(summary.group(1))
        if rec is None:
            continue
        rec.dt = datetime.strptime(
            dt.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        rec.summary = summary.group(1)
        events.append(rec)

    return events


def parse_years(years) -> list[Rec]:
    seen = set()
    events = []
    for year in years:
        for rec in parse(year):
            if (rec.summary, rec.dt) in seen:
                continue
            seen.add((rec.summary, rec.dt))
            events.append(rec)
    return sorted(events, key=lambda r: r.dt)
