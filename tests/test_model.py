from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from skyevents.model import Event, EventType, make_uid

DT = datetime(2026, 7, 3, 13, 2, tzinfo=timezone.utc)


def test_make_uid_is_deterministic():
    uid = make_uid(EventType.CLOSE_APPROACH, ["moon", "venus"], DT)
    assert uid == "close_approach:moon-venus:20260703"


def test_uid_body_order_is_canonical():
    """moon-venus and venus-moon must be one event, not two"""

    assert make_uid(
        EventType.CLOSE_APPROACH, ["venus", "moon"], DT
    ) == make_uid(EventType.CLOSE_APPROACH, ["moon", "venus"], DT)


def test_create_canonicalizes_bodies():
    event = Event.create(EventType.CLOSE_APPROACH, DT, ["venus", "moon"])
    assert event.bodies == ["moon", "venus"]
    assert event.uid == "close_approach:moon-venus:20260703"


def test_uid_ignores_time_of_day():
    """A refined peak instant must not change the event identity"""

    shifted = DT.replace(hour=23, minute=59)
    assert make_uid(EventType.MOON_PHASE, ["moon"], DT) == make_uid(
        EventType.MOON_PHASE, ["moon"], shifted
    )


def test_create_fills_uid_and_defaults():
    event = Event.create(EventType.MOON_PHASE, DT, ["moon"])
    assert event.uid == "moon_phase:moon:20260703"
    assert event.params == {}


def test_serialization_round_trip():
    event = Event.create(
        EventType.CLOSE_APPROACH,
        DT,
        ["moon", "venus"],
        {"separation_deg": 3.9},
    )
    restored = Event.model_validate_json(event.model_dump_json())
    assert restored == event


def test_naive_datetime_rejected():
    with pytest.raises(ValidationError):
        Event.create(EventType.MOON_PHASE, DT.replace(tzinfo=None), ["moon"])


def test_non_utc_timezone_rejected():
    msk = timezone(timedelta(hours=3))
    with pytest.raises(ValidationError):
        Event.create(EventType.MOON_PHASE, DT.astimezone(msk), ["moon"])
