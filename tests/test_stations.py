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
# agree with published retrograde calendars once each is converted out
# of whichever zone it renders in — astro-seek in US local time,
# in-the-sky.org in Berlin time, where Saturn's "11 Dec" direct station
# is our 2026-12-10 23:31 UTC.
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
        # date-derived, and three 2026 stations fall within an hour of
        # midnight (venus 00:27, saturn 23:31, jupiter 00:56), so a
        # shift in the definition would silently re-id them
        assert event.dt_utc.strftime("%Y-%m-%d") == date, (
            f"{body} {direction}: {event.dt_utc} vs published {date}")
    assert_unique_uids(events)


def test_verified_instants():
    events = stations.generate(2026)

    for text, body, direction, tol_minutes in VERIFIED_INSTANTS:
        # nearest rather than a fixed search radius: a regression large
        # enough to leave the radius would otherwise report "not found"
        # and swallow the one number that identifies the cause
        candidates = [e for e in events if e.bodies == [body]
                      and e.params["direction"] == direction]
        assert candidates, f"no {body} {direction} station in 2026 at all"
        nearest = min(candidates, key=lambda e: abs(e.dt_utc - ref_dt(text)))
        delta = abs((nearest.dt_utc - ref_dt(text)).total_seconds()) / 60
        assert delta <= tol_minutes, (
            f"{body} {direction}: {nearest.dt_utc} vs published {text} "
            f"({delta:.1f} min off, tolerance {tol_minutes})")


def test_conjunction_artifact_rejected():
    """A planet behind the Sun must not manufacture stations.

    Uranus's 2029 conjunction is near-exact (0.01° elongation), where
    the light-deflection term in apparent() makes the longitude jitter
    by arcminutes. Without the elongation floor the sign of the rate
    flips repeatedly and Uranus gains four stations within 2.5 hours on
    2029-06-04, on top of its two real ones.
    """

    uranus = [e for e in stations.generate(2029) if e.bodies[0] == "uranus"]

    assert [(e.dt_utc.strftime("%Y-%m-%d"), e.params["direction"])
            for e in uranus] == [("2029-02-16", "direct"),
                                 ("2029-09-23", "retrograde")]


def test_no_station_clusters():
    """Consecutive stations of one planet are months apart, never hours.

    The generic form of the artifact above: any numerical instability in
    the rate shows up as a tight cluster, and does so in pairs that the
    alternation check below cannot see.
    """

    for year in (2026, 2029):
        by_body = {}
        for event in stations.generate(year):
            by_body.setdefault(event.bodies[0], []).append(event.dt_utc)
        for body, times in by_body.items():
            for earlier, later in zip(sorted(times), sorted(times)[1:]):
                gap = (later - earlier).total_seconds() / 86400
                assert gap >= 10, (
                    f"{body} in {year}: stations {gap:.2f} days apart "
                    f"({earlier}, {later})")


def test_directions_alternate_per_planet():
    """A planet cannot station retrograde twice without turning back"""

    events = stations.generate(2026)

    for body in {e.bodies[0] for e in events}:
        directions = [e.params["direction"] for e in events
                      if e.bodies[0] == body]
        for earlier, later in zip(directions, directions[1:]):
            assert earlier != later, f"{body}: {directions}"
