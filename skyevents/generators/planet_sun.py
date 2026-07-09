"""Planet-Sun alignments.

Outer planets: opposition / conjunction. Mercury and Venus: inferior /
superior conjunction, told apart by the planet-Sun distance order.
"""

from skyfield import almanac
from skyfield.searchlib import find_discrete

from skyevents.generators.base import PLANETS, context
from skyevents.model import Event, EventType

INNER = ("mercury", "venus")


def generate(year: int) -> list[Event]:
    ctx = context()
    t0, t1 = ctx.year_window(year)

    events = []
    for name in PLANETS:
        f = almanac.oppositions_conjunctions(ctx.eph, ctx.planets[name])
        times, kinds = find_discrete(t0, t1, f)
        for t, is_opposition in zip(times, kinds):
            if name in INNER:
                e = ctx.earth.at(t)
                d_planet = e.observe(ctx.planets[name]).distance().km
                d_sun = e.observe(ctx.sun).distance().km
                kind = "inferior" if d_planet < d_sun else "superior"
            else:
                kind = "opposition" if is_opposition else "conjunction"
            events.append(
                Event.create(EventType.PLANET_SUN, t.utc_datetime(),
                             [name], {"kind": kind}))
    return sorted(events, key=lambda e: e.dt_utc)
