from skyevents.generators import planet_sun
from skyevents.model import EventType

from tests.util import assert_matches_reference, assert_unique_uids

# all 2026 events from the in-the-sky.org feed (stage-0 spike capture)
REFERENCE = [
    ("2026-01-06 17:10", "venus", "superior"),
    ("2026-01-09 11:07", "mars", "conjunction"),
    ("2026-01-10 08:34", "jupiter", "opposition"),
    ("2026-01-21 16:01", "mercury", "superior"),
    ("2026-03-07 10:57", "mercury", "inferior"),
    ("2026-03-22 11:09", "neptune", "conjunction"),
    ("2026-03-25 08:45", "saturn", "conjunction"),
    ("2026-05-14 14:30", "mercury", "superior"),
    ("2026-05-22 14:17", "uranus", "conjunction"),
    ("2026-07-13 01:20", "mercury", "inferior"),
    ("2026-07-29 12:06", "jupiter", "conjunction"),
    ("2026-08-27 17:11", "mercury", "superior"),
    ("2026-09-26 01:28", "neptune", "opposition"),
    ("2026-10-04 12:21", "saturn", "opposition"),
    ("2026-10-24 03:39", "venus", "inferior"),
    ("2026-11-04 14:20", "mercury", "inferior"),
    ("2026-11-25 22:33", "uranus", "opposition"),
]

TOL_MINUTES = 70


def test_2026_matches_feed_reference():
    events = planet_sun.generate(2026)

    def check(body, kind):
        def _check(event):
            assert event.type == EventType.PLANET_SUN
            assert event.bodies == [body]
            assert event.params["kind"] == kind
        return _check

    assert_matches_reference(
        events, [(dt, check(body, kind)) for dt, body, kind in REFERENCE],
        TOL_MINUTES)
    assert_unique_uids(events)
