from skyevents.generators import lunar_eclipses
from skyevents.model import EventType

from tests.util import assert_matches_reference, assert_unique_uids

# 2026 from the in-the-sky.org feed (stage-0 spike capture)
REFERENCE = [
    ("2026-03-03 11:34", "total"),
    ("2026-08-28 04:14", "partial"),
]

TOL_MINUTES = 3


def test_2026_matches_feed_reference():
    events = lunar_eclipses.generate(2026)

    def check(kind):
        def _check(event):
            assert event.type == EventType.LUNAR_ECLIPSE
            assert event.bodies == ["moon"]
            assert event.params["kind"] == kind
            if kind == "total":
                assert event.params["umbral_magnitude"] > 1
        return _check

    assert_matches_reference(
        events, [(dt, check(kind)) for dt, kind in REFERENCE],
        TOL_MINUTES)
    assert_unique_uids(events)


def test_2029_known_total_eclipses():
    """Independent reference: 2029 has totals on Jun 26 and Dec 20"""

    events = lunar_eclipses.generate(2029)
    totals = [e for e in events if e.params["kind"] == "total"]
    days = {e.dt_utc.strftime("%Y-%m-%d") for e in totals}
    assert {"2029-06-26", "2029-12-20"} <= days
