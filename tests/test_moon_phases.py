from skyevents.generators import moon_phases
from skyevents.model import EventType

from tests.util import assert_matches_reference, assert_unique_uids

# all 2026 phases from the in-the-sky.org feed (stage-0 spike capture)
REFERENCE = [
    ("2026-01-03 10:02", "full"),
    ("2026-01-10 15:48", "last_quarter"),
    ("2026-01-18 19:53", "new"),
    ("2026-01-26 04:47", "first_quarter"),
    ("2026-02-01 22:09", "full"),
    ("2026-02-09 12:43", "last_quarter"),
    ("2026-02-17 12:02", "new"),
    ("2026-02-24 12:28", "first_quarter"),
    ("2026-03-03 11:37", "full"),
    ("2026-03-11 09:39", "last_quarter"),
    ("2026-03-19 01:24", "new"),
    ("2026-03-25 19:18", "first_quarter"),
    ("2026-04-02 02:11", "full"),
    ("2026-04-10 04:52", "last_quarter"),
    ("2026-04-17 11:52", "new"),
    ("2026-04-24 02:32", "first_quarter"),
    ("2026-05-01 17:23", "full"),
    ("2026-05-09 21:11", "last_quarter"),
    ("2026-05-16 20:02", "new"),
    ("2026-05-23 11:11", "first_quarter"),
    ("2026-05-31 08:45", "full"),
    ("2026-06-08 10:01", "last_quarter"),
    ("2026-06-15 02:55", "new"),
    ("2026-06-21 21:55", "first_quarter"),
    ("2026-06-29 23:56", "full"),
    ("2026-07-07 19:29", "last_quarter"),
    ("2026-07-14 09:44", "new"),
    ("2026-07-21 11:06", "first_quarter"),
    ("2026-07-29 14:35", "full"),
    ("2026-08-06 02:21", "last_quarter"),
    ("2026-08-12 17:37", "new"),
    ("2026-08-20 02:46", "first_quarter"),
    ("2026-08-28 04:18", "full"),
    ("2026-09-04 07:51", "last_quarter"),
    ("2026-09-11 03:28", "new"),
    ("2026-09-18 20:44", "first_quarter"),
    ("2026-09-26 16:48", "full"),
    ("2026-10-03 13:25", "last_quarter"),
    ("2026-10-10 15:51", "new"),
    ("2026-10-18 16:13", "first_quarter"),
    ("2026-10-26 04:11", "full"),
    ("2026-11-01 20:28", "last_quarter"),
    ("2026-11-09 07:03", "new"),
    ("2026-11-17 11:48", "first_quarter"),
    ("2026-11-24 14:53", "full"),
    ("2026-12-01 06:09", "last_quarter"),
    ("2026-12-09 00:53", "new"),
    ("2026-12-17 05:43", "first_quarter"),
    ("2026-12-24 01:28", "full"),
    ("2026-12-30 18:59", "last_quarter"),
]

TOL_MINUTES = 3


def test_2026_matches_feed_reference():
    events = moon_phases.generate(2026)

    def check(phase):
        def _check(event):
            assert event.type == EventType.MOON_PHASE
            assert event.bodies == ["moon"]
            assert event.params["phase"] == phase
        return _check

    assert_matches_reference(
        events, [(dt, check(phase)) for dt, phase in REFERENCE],
        TOL_MINUTES)
    assert_unique_uids(events)
