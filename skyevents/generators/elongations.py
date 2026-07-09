"""Greatest elongations of Mercury and Venus.

Maxima of the geocentric Sun-planet angular separation. The feed's
instants differ by hours (different definition), so tests check the
elongation value tightly and the instant loosely.
"""

from skyfield.searchlib import find_maxima

from skyevents.generators.base import context, dedupe_extrema
from skyevents.model import Event, EventType


def generate(year: int) -> list[Event]:
    ctx = context()
    t0, t1 = ctx.year_window(year)

    events = []
    for name in ("mercury", "venus"):
        planet = ctx.planets[name]
        times, values = find_maxima(
            t0, t1, ctx.separation(planet, ctx.sun, 5.0))
        for t, elongation in dedupe_extrema(times, values):
            side = ("east" if (ctx.ecliptic_lon(t, planet)
                               - ctx.ecliptic_lon(t, ctx.sun)) % 360 < 180
                    else "west")
            events.append(Event.create(
                EventType.ELONGATION, t.utc_datetime(), [name],
                {"side": side, "elongation_deg": round(float(elongation), 2)}))
    return sorted(events, key=lambda e: e.dt_utc)
