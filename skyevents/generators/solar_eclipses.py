"""Solar eclipses: Sun-Moon separation minima around new moons.

The detection threshold is the sum of the apparent radii plus the
Moon's horizontal parallax — a plain geocentric criterion would miss
most partial eclipses visible only from part of Earth's surface.
The total/annular/partial kind is approximate: seen from the geocenter
the central kind is not reliable (hybrids by definition sit on the
boundary), so params carry the raw quantities too.
"""

from math import asin, degrees

from skyfield import almanac
from skyfield.searchlib import find_discrete, find_minima

from skyevents.generators.base import context
from skyevents.model import Event, EventType

R_SUN_KM = 696340.0
R_MOON_KM = 1737.4
R_EARTH_KM = 6378.14


def generate(year: int) -> list[Event]:
    ctx = context()
    t0, t1 = ctx.year_window(year)

    times, phases = find_discrete(t0, t1, almanac.moon_phases(ctx.eph))
    new_moons = [t for t, phase in zip(times, phases) if phase == 0]

    separation = ctx.separation(ctx.sun, ctx.moon, 0.05)
    events = []
    for new_moon in new_moons:
        lo = ctx.ts.tt_jd(new_moon.tt - 1.5)
        hi = ctx.ts.tt_jd(new_moon.tt + 1.5)
        t_min, sep_min = find_minima(lo, hi, separation)
        if len(t_min) == 0:
            continue
        t, sep = t_min[0], float(sep_min[0])

        e = ctx.earth.at(t)
        d_sun = e.observe(ctx.sun).distance().km
        d_moon = e.observe(ctx.moon).distance().km
        r_sun = degrees(asin(R_SUN_KM / d_sun))
        r_moon = degrees(asin(R_MOON_KM / d_moon))
        parallax = degrees(asin(R_EARTH_KM / d_moon))

        if sep >= r_sun + r_moon + parallax:
            continue
        # ratio of apparent radii for an observer with the Moon overhead
        ratio = degrees(asin(R_MOON_KM / (d_moon - R_EARTH_KM))) / r_sun
        if sep < parallax:
            kind = "total" if ratio >= 1 else "annular"
        else:
            kind = "partial"
        events.append(Event.create(
            EventType.SOLAR_ECLIPSE, t.utc_datetime(), ["sun", "moon"],
            {"kind": kind,
             "separation_deg": round(sep, 4),
             "radius_ratio": round(ratio, 4)}))
    return events
