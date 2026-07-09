from skyevents.generators import elongations
from skyevents.model import EventType

from tests.util import assert_matches_reference, assert_unique_uids

# all 2026 events from the in-the-sky.org feed (stage-0 spike capture);
# the feed computes the instant differently, hence the loose tolerance
REFERENCE = [
    ("2026-02-19 14:35", "mercury", "east"),
    ("2026-04-03 18:48", "mercury", "west"),
    ("2026-06-15 22:40", "mercury", "east"),
    ("2026-08-02 13:54", "mercury", "west"),
    ("2026-08-14 21:59", "venus", "east"),
    ("2026-10-12 05:50", "mercury", "east"),
    ("2026-11-21 00:33", "mercury", "west"),
]

TOL_MINUTES = 12 * 60

ELONGATION_DEG = {"mercury": (17.9, 28.1), "venus": (45.0, 47.5)}


def test_2026_matches_feed_reference():
    events = elongations.generate(2026)

    def check(body, side):
        def _check(event):
            assert event.type == EventType.ELONGATION
            assert event.bodies == [body]
            assert event.params["side"] == side
            lo, hi = ELONGATION_DEG[body]
            assert lo <= event.params["elongation_deg"] <= hi
        return _check

    assert_matches_reference(
        events, [(dt, check(body, side)) for dt, body, side in REFERENCE],
        TOL_MINUTES)
    assert_unique_uids(events)
