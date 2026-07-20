"""Moon phases: new, first quarter, full, last quarter"""

from skyfield import almanac

from skyevents.generators.base import context
from skyevents.model import Event, EventType

PHASES = ("new", "first_quarter", "full", "last_quarter")


def generate(year: int) -> list[Event]:
    ctx = context()
    t0, t1 = ctx.search_window(year)
    times, phases = almanac.find_discrete(
        t0, t1, almanac.moon_phases(ctx.eph))
    return [
        Event.create(EventType.MOON_PHASE, t.utc_datetime(), ["moon"],
                     {"phase": PHASES[phase]})
        for t, phase in zip(times, phases)
    ]
