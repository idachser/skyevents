"""Equinoxes and solstices"""

from skyfield import almanac

from skyevents.generators.base import context
from skyevents.model import Event, EventType

SEASONS = ("march_equinox", "june_solstice",
           "september_equinox", "december_solstice")


def generate(year: int) -> list[Event]:
    ctx = context()
    t0, t1 = ctx.search_window(year)
    times, seasons = almanac.find_discrete(
        t0, t1, almanac.seasons(ctx.eph))
    return [
        Event.create(EventType.SEASON, t.utc_datetime(), ["sun"],
                     {"season": SEASONS[season]})
        for t, season in zip(times, seasons)
    ]
