"""Comet events: perihelion, perigee, and peak brightness.

Three separate event types, not one with a `kind`: the uid is
`type:bodies:date`, and a comet whose perigee and brightness peak fall on
the same day (10P/Tempel does, in 2026) would collapse two events into
one if they shared a type.

A comet is published for a year only if it gets **brighter than
magnitude 12** at some point in it (~10 comets in 2026; the cut at 10
would give 5). Brightness is the MPC total-magnitude law
`m = g + 5*log10(delta) + 2.5*k*log10(r)`, with g and k the absolute
magnitude and slope from the elements, delta the geocentric and r the
heliocentric distance. For a qualifying comet all three events that fall
inside the year are emitted, each carrying the magnitude at its instant.

Positions are two-body propagation of the CometEls.txt elements (see
skyevents/comets.py), downloaded at runtime; with no local file there are
simply no comet events.
"""

from datetime import datetime, timezone

import numpy as np
from skyfield.searchlib import find_minima

from skyevents import comets
from skyevents.generators.base import context, dedupe_extrema
from skyevents.model import Event, EventType

# Comets brighten fast near perihelion, so the search steps finer than
# the asteroids' 20 days; find_minima still refines within each bracket.
STEP_DAYS = 5.0

# Widen the search past the year so find_minima can see a trend continue
# across a boundary instead of reporting the boundary itself as an
# extremum: 2P/Encke (perihelion 2027-02) is still brightening at the end
# of 2026, and an unpadded search would flag a spurious "peak" at the
# year's edge. Extrema are then kept only if their refined instant lands
# inside the year.
PAD_DAYS = 45.0

MAX_MAGNITUDE = 12.0


def _apparent_magnitude(g: float, k: float, delta_au: float,
                        r_au: float) -> float:
    """MPC total (m1) magnitude: g + 5*log10(delta) + 2.5*k*log10(r).

    numpy log10 so the same expression serves both a scalar instant and
    the time vectors find_minima evaluates the search function on.
    """

    return g + 5.0 * np.log10(delta_au) + 2.5 * k * np.log10(r_au)


def _brightest_possible(comet: comets.Comet) -> float:
    """A floor on the comet's magnitude over its whole orbit, or -inf.

    r >= q everywhere, and for q > 1 the comet stays outside the Earth's
    orbit, so its geocentric distance is at least q - 1 (two points at
    radii r >= q > 1 and ~1 AU are never closer than that). Both the
    5*log(delta) and 2.5*k*log(r) terms are then genuinely bounded below,
    so this can only overstate the brightness -- a comet whose floor is
    fainter than the cut is dropped without any ephemeris search, which
    is what keeps a full catalog's generation quick.

    For q <= 1 that bound collapses: the comet can cross the 1 AU sphere,
    so delta has no positive lower bound and no floor holds. Those few
    are always searched rather than risk pruning a faint object that
    turns bright on a close pass.
    """

    q = comet.perihelion_distance_au
    if q <= 1.0:
        return float("-inf")
    return _apparent_magnitude(comet.magnitude_g, comet.slope_k, q - 1.0, q)


def _measure(ctx, body, comet: comets.Comet, t):
    """(geocentric AU, heliocentric AU, magnitude) at instant t"""

    astrometric = ctx.earth.at(t).observe(body)
    delta = astrometric.distance().au
    r = ctx.sun.at(t).observe(body).distance().au
    return delta, r, _apparent_magnitude(
        comet.magnitude_g, comet.slope_k, delta, r)


def _event(kind: EventType, t, ctx, body, comet: comets.Comet) -> Event:
    delta, r, magnitude = _measure(ctx, body, comet, t)
    return Event.create(
        kind, t.utc_datetime(), [comet.slug],
        {"name": comet.designation,
         "magnitude": round(magnitude, 1),
         "distance_au": round(float(delta), 3),
         "heliocentric_au": round(float(r), 3)})


def generate(year: int) -> list[Event]:
    catalog = comets.load_catalog()
    if not catalog:
        return []

    ctx = context()
    t0, t1 = ctx.search_window(year, pad_days=PAD_DAYS, step_days=STEP_DAYS)
    year_start = datetime(year, 1, 1, tzinfo=timezone.utc)
    year_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

    def in_year(t):
        return year_start <= t.utc_datetime() < year_end

    events = []
    for comet in catalog:
        if _brightest_possible(comet) >= MAX_MAGNITUDE:
            continue
        body = ctx.sun + comets.orbit(comet, ctx.ts)

        # brightness minima (peaks) and geocentric-distance minima
        # (perigees). The padding lets find_minima see a trend continue
        # across a year edge instead of reporting the edge itself, so an
        # in-year extremum is a real one.
        def magnitude(t, body=body, comet=comet):
            return _measure(ctx, body, comet, t)[2]
        magnitude.step_days = STEP_DAYS

        def distance(t, body=body):
            return ctx.earth.at(t).observe(body).distance().au
        distance.step_days = STEP_DAYS

        ptimes, pmags = find_minima(t0, t1, magnitude)
        peaks = [(t, m) for t, m in dedupe_extrema(ptimes, pmags)
                 if in_year(t)]
        dtimes, dists = find_minima(t0, t1, distance)
        perigees = [(t, d) for t, d in dedupe_extrema(dtimes, dists)
                    if in_year(t)]
        perigee_t = min(perigees, key=lambda td: td[1])[0] if perigees else None

        # perihelion straight from the T element -- no search needed
        peri_t = ctx.ts.tt(comet.perihelion_year, comet.perihelion_month,
                           comet.perihelion_day)
        perihelion_t = peri_t if in_year(peri_t) else None

        # A comet counts for the year if it beats the cut at any of its
        # in-year event instants -- not only at a brightness peak. When
        # the peak sits just across a boundary (within PAD_DAYS) and only
        # the perihelion or perigee falls inside, those events must still
        # be emitted rather than the whole comet dropped.
        candidates = [m for _, m in peaks]
        if perihelion_t is not None:
            candidates.append(_measure(ctx, body, comet, perihelion_t)[2])
        if perigee_t is not None:
            candidates.append(_measure(ctx, body, comet, perigee_t)[2])
        if not candidates or round(min(candidates), 1) >= MAX_MAGNITUDE:
            continue

        # the peak-brightness event stays gated on its own magnitude: it
        # names the brightest instant, so a sub-threshold "peak" would be
        # a contradiction, even when the comet qualifies via its perigee
        if peaks:
            peak_t, peak_m = min(peaks, key=lambda tm: tm[1])
            if round(peak_m, 1) < MAX_MAGNITUDE:
                events.append(_event(
                    EventType.COMET_PEAK_BRIGHTNESS, peak_t, ctx, body, comet))
        if perihelion_t is not None:
            events.append(_event(
                EventType.COMET_PERIHELION, perihelion_t, ctx, body, comet))
        if perigee_t is not None:
            events.append(_event(
                EventType.COMET_PERIGEE, perigee_t, ctx, body, comet))

    return sorted(events, key=lambda e: e.dt_utc)
