from skyevents.generators import lunar_apsides
from skyevents.model import EventType

from tests.util import assert_matches_reference, assert_unique_uids

# all 2026 apsides from the in-the-sky.org feed (stage-0 spike capture)
REFERENCE = [
    ("2026-01-01 21:44", "perigee"),
    ("2026-01-13 20:46", "apogee"),
    ("2026-01-29 21:45", "perigee"),
    ("2026-02-10 16:51", "apogee"),
    ("2026-02-24 23:14", "perigee"),
    ("2026-03-10 13:42", "apogee"),
    ("2026-03-22 11:39", "perigee"),
    ("2026-04-07 08:30", "apogee"),
    ("2026-04-19 06:55", "perigee"),
    ("2026-05-04 22:30", "apogee"),
    ("2026-05-17 13:43", "perigee"),
    ("2026-06-01 04:32", "apogee"),
    ("2026-06-14 23:19", "perigee"),
    ("2026-06-28 07:10", "apogee"),
    ("2026-07-13 07:56", "perigee"),
    ("2026-07-25 16:45", "apogee"),
    ("2026-08-10 11:17", "perigee"),
    ("2026-08-22 08:20", "apogee"),
    ("2026-09-06 20:42", "perigee"),
    ("2026-09-19 03:00", "apogee"),
    ("2026-10-01 20:51", "perigee"),
    ("2026-10-16 22:55", "apogee"),
    ("2026-10-28 18:05", "perigee"),
    ("2026-11-13 17:50", "apogee"),
    ("2026-11-25 21:01", "perigee"),
    ("2026-12-11 06:45", "apogee"),
    ("2026-12-24 08:31", "perigee"),
]

TOL_MINUTES = 35

# Earth-Moon distance stays within these bounds
PERIGEE_KM = (356000, 371000)
APOGEE_KM = (404000, 407000)


def test_2026_matches_feed_reference():
    events = lunar_apsides.generate(2026)

    def check(kind):
        def _check(event):
            assert event.type == EventType.LUNAR_APSIS
            assert event.bodies == ["moon"]
            assert event.params["kind"] == kind
            lo, hi = PERIGEE_KM if kind == "perigee" else APOGEE_KM
            assert lo <= event.params["distance_km"] <= hi
        return _check

    assert_matches_reference(
        events, [(dt, check(kind)) for dt, kind in REFERENCE],
        TOL_MINUTES)
    assert_unique_uids(events)
