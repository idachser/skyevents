"""Retrograde and direct stations of the planets.

A station is the instant a planet stops moving one way along the
ecliptic and reverses: retrograde when eastward motion turns westward,
direct when it turns back.

Longitude, not right ascension, is what reverses here. The two differ by
far more than they look: taking RA instead puts Saturn's 2026 retrograde
station 27 *hours* from the feed's, because near the equinoxes the
projection onto the equator distorts a rate that is passing through
zero. For the same reason the instant is intrinsically soft — aberration
and the choice of equinox move it by tens of minutes each (apparent vs
astrometric, equinox of date vs J2000, span roughly two hours for
Saturn), so the tests allow 45 minutes against a source computing the
instant differently and 5 against one computing it as we do. We take
apparent longitude referred to the equinox of date, the classical
definition and the closest match to the feed.
"""

from skyfield.searchlib import find_discrete

from skyevents.generators.base import PLANETS, context
from skyevents.model import Event, EventType

# half-width of the central difference used for the longitude rate
DELTA_DAYS = 0.05

# Mercury's retrograde arcs are the shortest at ~21 days, so its pair of
# stations bounds the coarse scan step every other planet inherits.
STEP_DAYS = 4.0

# A planet passing behind the Sun breaks the light-deflection term in
# Skyfield's apparent(): at Uranus's near-exact 2029 conjunction (0.01°
# elongation) the longitude jitters by arcminutes and the rate flips
# sign repeatedly, manufacturing four false stations within 2.5 hours.
# The corruption is confined to roughly 0.1°, while every genuine
# station stands well clear of the Sun — an outer planet stations near
# opposition, and the closest any Mercury station comes over 2025-2030
# is 14.75° — so this floor drops the artifact and nothing real.
MIN_SUN_ELONGATION_DEG = 1.0


def _prograde(ctx, planet):
    """True while the planet's apparent ecliptic longitude is increasing"""

    def f(t):
        before = ctx.ecliptic_lon(ctx.ts.tt_jd(t.tt - DELTA_DAYS), planet)
        after = ctx.ecliptic_lon(ctx.ts.tt_jd(t.tt + DELTA_DAYS), planet)
        # longitude wraps at 360°; no planet moves near 180° per step
        return ((after - before + 180.0) % 360.0 - 180.0) > 0.0

    f.step_days = STEP_DAYS
    return f


def generate(year: int) -> list[Event]:
    ctx = context()
    # find_discrete samples only within the window it is handed, so the
    # sole reach past the edge is the central difference — no need for
    # the full step the find_minima/find_maxima generators must reserve
    t0, t1 = ctx.search_window(year, step_days=DELTA_DAYS)

    events = []
    for name in PLANETS:
        planet = ctx.planets[name]
        times, prograde = find_discrete(t0, t1, _prograde(ctx, planet))
        for t, is_prograde in zip(times, prograde):
            e = ctx.earth.at(t)
            elongation = e.observe(planet).separation_from(
                e.observe(ctx.sun)).degrees
            if elongation < MIN_SUN_ELONGATION_DEG:
                continue
            # find_discrete reports the value the function takes *after*
            # each transition: back to prograde is the direct station
            direction = "direct" if is_prograde else "retrograde"
            events.append(Event.create(
                EventType.STATION, t.utc_datetime(), [name],
                {"direction": direction}))
    return sorted(events, key=lambda e: e.dt_utc)
