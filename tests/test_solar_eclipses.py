from functools import cache

from skyevents.generators import solar_eclipses
from skyevents.model import EventType

from tests.util import assert_matches_reference, assert_unique_uids

# several tests cover the same years; each generate() is a full-year
# moon-phase sweep plus a minima search per new moon
generate = cache(solar_eclipses.generate)

# 2026 from the in-the-sky.org feed (stage-0 spike capture)
REFERENCE = [
    ("2026-02-17 12:12", "annular"),
    ("2026-08-12 17:47", "total"),
]

TOL_MINUTES = 3


def test_2026_matches_feed_reference():
    events = generate(2026)

    def check(kind):
        def _check(event):
            assert event.type == EventType.SOLAR_ECLIPSE
            assert event.bodies == ["sun", "moon"]
            assert event.params["kind"] == kind
            ratio = event.params["radius_ratio"]
            assert ratio > 1 if kind == "total" else ratio < 1
        return _check

    assert_matches_reference(
        events, [(dt, check(kind)) for dt, kind in REFERENCE],
        TOL_MINUTES)
    assert_unique_uids(events)


def test_2027_known_eclipses():
    """Independent reference: annular Feb 6 and total Aug 2, 2027"""

    events = generate(2027)
    by_day = {e.dt_utc.strftime("%Y-%m-%d"): e.params["kind"]
              for e in events}
    assert by_day["2027-02-06"] == "annular"
    assert by_day["2027-08-02"] == "total"


def test_ephemeris_edge_years_do_not_crash():
    """The widened search window must clamp to ephemeris coverage:
    2025 and 2030 are the edge years of the committed excerpt."""

    for year, days in ((2025, ["2025-03-29", "2025-09-21"]),
                       (2030, ["2030-06-01", "2030-11-25"])):
        events = generate(year)
        assert [e.dt_utc.strftime("%Y-%m-%d") for e in events] == days


def test_year_boundary_no_misses_or_duplicates():
    """The new-moon search is wider than the year; each eclipse must
    land in exactly one year — the one containing the minimum."""

    across_years = []
    for year in (2026, 2027, 2028):
        events = generate(year)
        assert all(e.dt_utc.year == year for e in events)
        across_years += events
    assert_unique_uids(across_years)
