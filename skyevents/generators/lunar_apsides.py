"""Lunar perigees and apogees: extrema of the Earth-Moon distance"""

from skyfield.searchlib import find_maxima, find_minima

from skyevents.generators.base import context, dedupe_extrema
from skyevents.model import Event, EventType


def generate(year: int) -> list[Event]:
    ctx = context()
    t0, t1 = ctx.year_window(year)

    def distance_km(t):
        return ctx.earth.at(t).observe(ctx.moon).distance().km

    distance_km.step_days = 5.0

    events = []
    for finder, kind in ((find_minima, "perigee"), (find_maxima, "apogee")):
        times, distances = finder(t0, t1, distance_km)
        events += [
            Event.create(EventType.LUNAR_APSIS, t.utc_datetime(), ["moon"],
                         {"kind": kind, "distance_km": round(float(d), 1)})
            for t, d in dedupe_extrema(times, distances)
        ]
    return sorted(events, key=lambda e: e.dt_utc)
