"""Close approaches: minima of pairwise geocentric angular separation.

Only the separation minimum is generated; the feed's second per-pair
event, the RA-equality "conjunction", is deliberately not (stage-0
decision). Thresholds by pair class and the solar-elongation filter
follow the stage-0 diff: the feed never publishes Moon pairs with the
dim planets and drops pairs unobservable near the Sun.
"""

from itertools import combinations

from skyfield.searchlib import find_minima

from skyevents.generators.base import PLANETS, context, dedupe_extrema
from skyevents.model import Event, EventType

DIM_PLANETS = ("uranus", "neptune")

MOON_PLANET_DEG = 7.0
PLANET_PLANET_DEG = 2.5
DIM_PAIR_DEG = 1.0
MIN_SUN_ELONGATION_DEG = 15.0


def threshold(a: str, b: str) -> float:
    if a in DIM_PLANETS or b in DIM_PLANETS:
        return DIM_PAIR_DEG
    if a == "moon":
        return MOON_PLANET_DEG
    return PLANET_PLANET_DEG


def generate(year: int) -> list[Event]:
    ctx = context()
    t0, t1 = ctx.year_window(year)

    pairs = [("moon", planet, 2.0) for planet in PLANETS]
    pairs += [(a, b, 5.0) for a, b in combinations(PLANETS, 2)]

    events = []
    for a, b, step_days in pairs:
        body_a, body_b = ctx.body(a), ctx.body(b)
        times, separations = find_minima(
            t0, t1, ctx.separation(body_a, body_b, step_days))
        for t, sep in dedupe_extrema(times, separations):
            if sep >= threshold(a, b):
                continue
            e = ctx.earth.at(t)
            sun = e.observe(ctx.sun)
            elongation = min(
                e.observe(body_a).separation_from(sun).degrees,
                e.observe(body_b).separation_from(sun).degrees)
            if elongation < MIN_SUN_ELONGATION_DEG:
                continue
            events.append(Event.create(
                EventType.CLOSE_APPROACH, t.utc_datetime(), [a, b],
                {"separation_deg": round(float(sep), 2),
                 "sun_elongation_deg": round(float(elongation), 1)}))
    return sorted(events, key=lambda e: e.dt_utc)
