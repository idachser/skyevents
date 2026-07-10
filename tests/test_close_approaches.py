from datetime import timedelta

from skyevents.generators import close_approaches
from skyevents.model import EventType, canonical_bodies

from tests.util import assert_unique_uids, ref_dt

# All 2026 close approaches from the in-the-sky.org feed (stage-0
# spike capture). The feed's Moon-Saturn-Neptune triple on 01-23 is
# represented by its Moon-Saturn pair; Moon-Neptune stays under our
# 1-degree dim-planet threshold. Our composition is a superset: the
# feed curates harder (roughly, pairs it deems unobservable).
FEED_2026 = [
    ("2026-01-03 23:13", ("moon", "jupiter")),
    ("2026-01-23 08:57", ("moon", "saturn")),
    ("2026-01-31 03:38", ("moon", "jupiter")),
    ("2026-02-18 23:10", ("moon", "mercury")),
    ("2026-02-27 07:31", ("moon", "jupiter")),
    ("2026-03-26 13:19", ("moon", "jupiter")),
    ("2026-04-20 11:28", ("mercury", "saturn")),
    ("2026-04-22 23:13", ("moon", "jupiter")),
    ("2026-05-13 17:32", ("moon", "saturn")),
    ("2026-05-19 02:03", ("moon", "venus")),
    ("2026-05-20 13:46", ("moon", "jupiter")),
    ("2026-06-09 19:48", ("venus", "jupiter")),
    ("2026-06-10 06:49", ("moon", "saturn")),
    ("2026-06-17 07:58", ("moon", "jupiter")),
    ("2026-06-17 20:30", ("moon", "venus")),
    ("2026-07-04 06:11", ("mars", "uranus")),
    ("2026-07-07 16:32", ("moon", "saturn")),
    ("2026-07-11 13:24", ("moon", "mars")),
    ("2026-07-17 14:47", ("moon", "venus")),
    ("2026-08-03 22:37", ("moon", "saturn")),
    ("2026-08-09 05:48", ("moon", "mars")),
    ("2026-08-16 06:56", ("moon", "venus")),
    ("2026-08-31 02:32", ("moon", "saturn")),
    ("2026-09-06 19:28", ("moon", "mars")),
    ("2026-09-08 18:44", ("moon", "jupiter")),
    ("2026-09-14 11:34", ("moon", "venus")),
    ("2026-09-27 06:35", ("moon", "saturn")),
    ("2026-10-05 06:11", ("moon", "mars")),
    ("2026-10-06 10:23", ("moon", "jupiter")),
    ("2026-10-24 12:23", ("moon", "saturn")),
    ("2026-11-02 13:39", ("moon", "mars")),
    ("2026-11-02 22:45", ("moon", "jupiter")),
    ("2026-11-16 02:04", ("mars", "jupiter")),
    ("2026-11-20 20:02", ("moon", "saturn")),
    ("2026-11-30 08:24", ("moon", "jupiter")),
    ("2026-11-30 16:54", ("moon", "mars")),
    ("2026-12-18 04:37", ("moon", "saturn")),
    ("2026-12-27 16:25", ("moon", "jupiter")),
    ("2026-12-28 13:28", ("moon", "mars")),
]

TOL = timedelta(hours=8)

TOTAL_2026 = 60  # regression pin for composition changes


def test_2026_contains_every_feed_event():
    events = close_approaches.generate(2026)
    for text, bodies in FEED_2026:
        expected_dt = ref_dt(text)
        found = [e for e in events
                 if e.bodies == list(bodies)
                 and abs(e.dt_utc - expected_dt) <= TOL]
        assert found, f"feed event {text} {bodies} not generated"


def test_2026_invariants():
    events = close_approaches.generate(2026)
    assert len(events) == TOTAL_2026
    for e in events:
        assert e.type == EventType.CLOSE_APPROACH
        assert e.bodies == canonical_bodies(e.bodies)
        sep = e.params["separation_deg"]
        assert sep < close_approaches.threshold(*e.bodies)
        assert (e.params["sun_elongation_deg"]
                >= close_approaches.MIN_SUN_ELONGATION_DEG)
    assert_unique_uids(events)
