from skyevents.generators import seasons
from skyevents.model import EventType

from tests.util import assert_matches_reference, assert_unique_uids

# 2026 from the in-the-sky.org feed (stage-0 spike capture)
REFERENCE = [
    ("2026-03-20 14:48", "march_equinox"),
    ("2026-06-21 08:27", "june_solstice"),
    ("2026-09-23 00:08", "september_equinox"),
    ("2026-12-21 20:53", "december_solstice"),
]

TOL_MINUTES = 10


def test_2026_matches_feed_reference():
    events = seasons.generate(2026)

    def check(season):
        def _check(event):
            assert event.type == EventType.SEASON
            assert event.bodies == ["sun"]
            assert event.params["season"] == season
        return _check

    assert_matches_reference(
        events, [(dt, check(season)) for dt, season in REFERENCE],
        TOL_MINUTES)
    assert_unique_uids(events)
