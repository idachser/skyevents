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
Saturn), which is why the tests allow hours rather than minutes. We take
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
    t0, t1 = ctx.search_window(year, step_days=STEP_DAYS + DELTA_DAYS)

    events = []
    for name in PLANETS:
        times, prograde = find_discrete(
            t0, t1, _prograde(ctx, ctx.planets[name]))
        for t, is_prograde in zip(times, prograde):
            # find_discrete reports the value the function takes *after*
            # each transition: back to prograde is the direct station
            direction = "direct" if is_prograde else "retrograde"
            events.append(Event.create(
                EventType.STATION, t.utc_datetime(), [name],
                {"direction": direction}))
    return sorted(events, key=lambda e: e.dt_utc)
