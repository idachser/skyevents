from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, field_validator


class EventType(StrEnum):
    MOON_PHASE = "moon_phase"
    SEASON = "season"
    LUNAR_APSIS = "lunar_apsis"
    PLANET_SUN = "planet_sun"
    ELONGATION = "elongation"
    CLOSE_APPROACH = "close_approach"
    LUNAR_ECLIPSE = "lunar_eclipse"
    SOLAR_ECLIPSE = "solar_eclipse"
    METEOR_SHOWER = "meteor_shower"
    STATION = "station"


# canonical body order: Sun, Moon, planets outward; anything else
# (stars, one day) after them alphabetically
BODY_RANK = {name: rank for rank, name in enumerate(
    ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
     "uranus", "neptune"))}


def canonical_bodies(bodies: list[str]) -> list[str]:
    """Fixed body order so moon-venus and venus-moon share one uid"""

    return sorted(bodies, key=lambda b: (BODY_RANK.get(b, len(BODY_RANK)), b))


def make_uid(type: EventType, bodies: list[str], dt_utc: datetime) -> str:
    """Deterministic uid: stable across regenerations of the same event.

    The date (not the exact time) goes into the uid so that a refined
    peak instant does not change the event's identity.
    """

    return ":".join([type, "-".join(canonical_bodies(bodies)),
                     dt_utc.strftime("%Y%m%d")])


class Event(BaseModel):
    uid: str
    type: EventType
    dt_utc: datetime
    bodies: list[str]
    params: dict[str, float | int | str] = {}

    @field_validator("dt_utc")
    @classmethod
    def must_be_utc(cls, value: datetime) -> datetime:
        if value.utcoffset() != timezone.utc.utcoffset(None):
            raise ValueError("dt_utc must be timezone-aware UTC")
        return value

    @classmethod
    def create(
        cls,
        type: EventType,
        dt_utc: datetime,
        bodies: list[str],
        params: dict | None = None,
    ) -> "Event":
        return cls(
            uid=make_uid(type, bodies, dt_utc),
            type=type,
            dt_utc=dt_utc,
            bodies=canonical_bodies(bodies),
            params=params or {},
        )
