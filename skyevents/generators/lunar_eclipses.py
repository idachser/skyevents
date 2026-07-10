"""Lunar eclipses via skyfield.eclipselib.

The module is marked experimental upstream; the exact Skyfield version
is pinned in uv.lock and the tests cover known eclipses, so an upstream
behavior change fails loudly.
"""

from skyfield import eclipselib

from skyevents.generators.base import context
from skyevents.model import Event, EventType

KINDS = ("penumbral", "partial", "total")


def generate(year: int) -> list[Event]:
    ctx = context()
    t0, t1 = ctx.year_window(year)
    times, kinds, details = eclipselib.lunar_eclipses(t0, t1, ctx.eph)
    return [
        Event.create(
            EventType.LUNAR_ECLIPSE, t.utc_datetime(), ["moon"],
            {"kind": KINDS[kind],
             "umbral_magnitude": round(
                 float(details["umbral_magnitude"][i]), 3),
             "penumbral_magnitude": round(
                 float(details["penumbral_magnitude"][i]), 3)})
        for i, (t, kind) in enumerate(zip(times, kinds))
    ]
