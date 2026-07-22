"""Oppositions of the bright minor planets.

The instant is the **maximum of solar elongation**, not the equality of
ecliptic longitudes that `planet_sun` uses for the planets. For a low
inclination the two agree, but Pallas (i = 34.9 deg) has them 2.4 days
apart -- and the in-the-sky.org feed the stage-0 spike calibrated
against sits on the elongation maximum (2026-10-04 14:22 in the feed,
14:17 here; the longitude opposition is 10-06, the right-ascension one
10-14). The elongation maximum is also the observationally meaningful
moment: closest, brightest, up all night.

Only oppositions brighter than magnitude 10 are published. That cut is
calibrated, not invented: the feed publishes Irene at 9.3 and Fides at
9.5 but drops Parthenope at 10.0 and Nysa at 10.1, and it reproduces
the feed's 2026-2027 composition apart from Eunomia (9.9 here, absent
there) -- one borderline object, as with close approaches.

Positions are two-body propagation of the committed MPCORB elements
(see skyevents/mpc.py), so the catalog ages; tests/test_asteroids.py
fails when its epoch grows stale.
"""

from functools import cache
from math import exp, log10, tan
from pathlib import Path

from skyfield.searchlib import find_maxima

from skyevents import mpc
from skyevents.generators.base import context, dedupe_extrema
from skyevents.model import Event, EventType

CATALOG = Path(__file__).with_name("asteroids.dat")

STEP_DAYS = 20.0
MAX_MAGNITUDE = 10.0

# An elongation maximum this far from opposition belongs to an object
# that never comes into opposition during the year -- the search would
# otherwise report the year's best moment as if it were an event. The
# floor has room to spare: inclination is what keeps a real opposition
# short of 180 deg, and Pallas, the most inclined object in the catalog
# (34.9 deg), still peaks at 159 deg.
MIN_ELONGATION_DEG = 140.0


@cache
def catalog() -> list[mpc.MinorPlanet]:
    # latin-1 rather than ascii: MPCORB is an ascii format, but one
    # stray byte in a name must not take down a whole year's generation
    with CATALOG.open(encoding="latin-1") as lines:
        return mpc.parse(lines)


def apparent_magnitude(h: float, g: float, r_au: float, delta_au: float,
                       phase_rad: float) -> float:
    """V magnitude in the IAU H-G system (Bowell et al. 1989).

    The phase angle is small at opposition but not zero -- 7.3 deg for
    Pallas, worth 0.4 mag, which straddles the publication cut.
    """

    tan_half = tan(phase_rad / 2.0)
    phi1 = exp(-3.33 * tan_half ** 0.63)
    phi2 = exp(-1.87 * tan_half ** 1.22)
    return (h + 5.0 * log10(r_au * delta_au)
            - 2.5 * log10((1.0 - g) * phi1 + g * phi2))


def generate(year: int) -> list[Event]:
    ctx = context()
    t0, t1 = ctx.search_window(year, step_days=STEP_DAYS)

    events = []
    for planet in catalog():
        body = ctx.sun + mpc.orbit(planet, ctx.ts)
        times, elongations = find_maxima(
            t0, t1, ctx.separation(body, ctx.sun, STEP_DAYS))
        for t, elongation in dedupe_extrema(times, elongations):
            if elongation < MIN_ELONGATION_DEG:
                continue
            astrometric = ctx.earth.at(t).observe(body)
            delta = astrometric.distance().au
            r = ctx.sun.at(t).observe(body).distance().au
            magnitude = apparent_magnitude(
                planet.magnitude_h, planet.slope_g, r, delta,
                astrometric.phase_angle(ctx.sun).radians)
            if magnitude >= MAX_MAGNITUDE:
                continue
            events.append(Event.create(
                EventType.ASTEROID_OPPOSITION, t.utc_datetime(),
                [planet.slug],
                {"number": planet.number, "name": planet.name,
                 "magnitude": round(magnitude, 1),
                 "distance_au": round(float(delta), 3),
                 "elongation_deg": round(float(elongation), 1)}))
    return sorted(events, key=lambda e: e.dt_utc)
