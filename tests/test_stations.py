"""Retrograde/direct stations.

No stage-0 feed capture exists for this type — the spike filtered
stations out — so the reference here was assembled from published
station calendars instead (in-the-sky.org for Saturn, astro-seek for
Mercury and Venus), all converted to UTC.
"""

from skyevents.generators import stations
from skyevents.model import EventType

from tests.util import assert_unique_uids, ref_dt

# every 2026 station, in order: (UTC date, body, direction). The dates
# agree with published retrograde calendars once those are converted
# out of US local time.
REFERENCE = [
    ("2026-02-04", "uranus", "direct"),
    ("2026-02-26", "mercury", "retrograde"),
    ("2026-03-11", "jupiter", "direct"),
    ("2026-03-20", "mercury", "direct"),
    ("2026-06-29", "mercury", "retrograde"),
    ("2026-07-07", "neptune", "retrograde"),
    ("2026-07-23", "mercury", "direct"),
    ("2026-07-26", "saturn", "retrograde"),
    ("2026-09-10", "uranus", "retrograde"),
    ("2026-10-03", "venus", "retrograde"),
    ("2026-10-24", "mercury", "retrograde"),
    ("2026-11-13", "mercury", "direct"),
    ("2026-11-14", "venus", "direct"),
    ("2026-12-10", "saturn", "direct"),
    ("2026-12-12", "neptune", "direct"),
    ("2026-12-13", "jupiter", "retrograde"),
]

# Instants published to the minute. Mercury's two come from an ephemeris
# using the same definition we do and agree exactly; Saturn's is the
# in-the-sky.org value, which sits 27 min off — the definitional spread
# described in the generator docstring, not an error either side.
VERIFIED_INSTANTS = [
    ("2026-07-26 19:29", "saturn", "retrograde", 45),
    ("2026-10-24 07:12", "mercury", "retrograde", 5),
    ("2026-11-13 15:53", "mercury", "direct", 5),
]


def test_2026_matches_published_stations():
    events = stations.generate(2026)

    assert len(events) == len(REFERENCE), (
        f"expected {len(REFERENCE)} stations, got "
        f"{[e.uid for e in events]}")
    for event, (date, body, direction) in zip(events, REFERENCE):
        assert event.type == EventType.STATION
        assert event.bodies == [body]
        assert event.params["direction"] == direction
        # the UTC date, not just the instant: a station's uid is
        # date-derived, and several 2026 stations fall within an hour of
        # midnight, so a shift in the definition would silently re-id them
        assert event.dt_utc.strftime("%Y-%m-%d") == date, (
            f"{body} {direction}: {event.dt_utc} vs published {date}")
    assert_unique_uids(events)


def test_verified_instants():
    events = stations.generate(2026)

    for text, body, direction, tol_minutes in VERIFIED_INSTANTS:
        matches = [e for e in events if e.bodies == [body]
                   and e.params["direction"] == direction
                   and abs((e.dt_utc - ref_dt(text)).total_seconds())
                   < 36 * 3600]
        assert len(matches) == 1, f"no unique {body} {direction} near {text}"
        delta = abs((matches[0].dt_utc - ref_dt(text)).total_seconds()) / 60
        assert delta <= tol_minutes, (
            f"{body} {direction}: {matches[0].dt_utc} vs published {text} "
            f"({delta:.1f} min off, tolerance {tol_minutes})")


def test_directions_alternate_per_planet():
    """A planet cannot station retrograde twice without turning back"""

    events = stations.generate(2026)

    for body in {e.bodies[0] for e in events}:
        directions = [e.params["direction"] for e in events
                      if e.bodies[0] == body]
        for earlier, later in zip(directions, directions[1:]):
            assert earlier != later, f"{body}: {directions}"
