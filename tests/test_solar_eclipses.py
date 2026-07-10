from skyevents.generators import solar_eclipses
from skyevents.model import EventType

from tests.util import assert_matches_reference, assert_unique_uids

# 2026 from the in-the-sky.org feed (stage-0 spike capture)
REFERENCE = [
    ("2026-02-17 12:12", "annular"),
    ("2026-08-12 17:47", "total"),
]

TOL_MINUTES = 3


def test_2026_matches_feed_reference():
    events = solar_eclipses.generate(2026)

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

    events = solar_eclipses.generate(2027)
    by_day = {e.dt_utc.strftime("%Y-%m-%d"): e.params["kind"]
              for e in events}
    assert by_day["2027-02-06"] == "annular"
    assert by_day["2027-08-02"] == "total"
