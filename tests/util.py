"""Helpers for generator tests.

Reference instants come from the in-the-sky.org feed captured during
the stage-0 spike; tolerances are the ones fixed in the plan.
"""

from datetime import datetime, timezone


def ref_dt(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(
        tzinfo=timezone.utc)


def assert_matches_reference(events, reference, tol_minutes):
    """events and reference must agree 1:1, in order, within tolerance.

    reference is a list of ("YYYY-MM-DD HH:MM", check) pairs where
    check(event) asserts type-specific fields.
    """

    assert len(events) == len(reference), (
        f"expected {len(reference)} events, got {len(events)}: "
        f"{[e.uid for e in events]}")
    for event, (text, check) in zip(events, reference):
        delta = abs((event.dt_utc - ref_dt(text)).total_seconds()) / 60
        assert delta <= tol_minutes, (
            f"{event.uid}: {event.dt_utc} vs reference {text} "
            f"({delta:.1f} min off, tolerance {tol_minutes})")
        check(event)


def assert_unique_uids(events):
    uids = [e.uid for e in events]
    assert len(set(uids)) == len(uids)
