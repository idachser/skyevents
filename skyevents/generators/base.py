"""Shared machinery for the per-type event generators.

All computations are geocentric, matching the in-the-sky.org feed the
stage-0 spike was calibrated against.
"""

from functools import cache

from skyfield.framelib import ecliptic_frame

from skyevents.ephemeris import load_ephemeris, load_timescale
from skyevents.model import BODY_RANK

PLANETS = tuple(b for b in BODY_RANK if b not in ("sun", "moon"))


class Context:
    """Loaded ephemeris plus the handles every generator needs"""

    def __init__(self):
        self.eph = load_ephemeris()
        self.ts = load_timescale()
        self.earth = self.eph["earth"]
        self.sun = self.eph["sun"]
        self.moon = self.eph["moon"]
        self.planets = {
            name: self.eph[name if name in ("mercury", "venus")
                           else f"{name} barycenter"]
            for name in PLANETS
        }
        segments = self.eph.spk.segments
        self.coverage = (max(s.start_jd for s in segments),
                         min(s.end_jd for s in segments))

    def body(self, name):
        if name == "sun":
            return self.sun
        if name == "moon":
            return self.moon
        return self.planets[name]

    def year_window(self, year: int):
        """Half-open [Jan 1 UTC, Jan 1 UTC of the next year)"""

        return self.ts.utc(year, 1, 1), self.ts.utc(year + 1, 1, 1)

    def search_window(self, year: int, pad_days: float = 0.0,
                      step_days: float = 0.0):
        """year_window widened by pad_days, clamped to ephemeris coverage.

        find_minima/find_maxima deliberately sample one step outside the
        window they are handed, and the ephemeris raises rather than
        extrapolate, so the clamp keeps step_days clear of the segment
        edges (plus a minute: skyfield samples in TDB, milliseconds off
        our TT instants). Pass the step_days of the search that will run
        on the window; searches near the edge of an ephemeris therefore
        miss events in its first and last step_days.
        """

        t0, t1 = self.year_window(year)
        start, end = self.coverage
        margin = step_days + 1.0 / 1440
        lo = max(t0.tt - pad_days, start + margin)
        hi = min(t1.tt + pad_days, end - margin)
        # the year itself must be searchable, not just its padding —
        # otherwise a year past the edge yields a sliver of the previous
        # one and the generator reports "no events" instead of failing
        if t1.tt <= lo or t0.tt >= hi:
            fmt = "%Y-%m-%d %H:%M"
            raise ValueError(
                f"year {year} is outside the ephemeris coverage "
                f"{self.ts.tt_jd(start).utc_strftime(fmt)}..."
                f"{self.ts.tt_jd(end).utc_strftime(fmt)}")
        return self.ts.tt_jd(lo), self.ts.tt_jd(hi)

    def ecliptic_lon(self, t, body) -> float:
        """Apparent ecliptic longitude of date, degrees"""

        pos = self.earth.at(t).observe(body).apparent()
        _, lon, _ = pos.frame_latlon(ecliptic_frame)
        return lon.degrees

    def separation(self, a, b, step_days: float):
        """Angular-separation-in-degrees function for skyfield.searchlib"""

        def f(t):
            e = self.earth.at(t)
            return e.observe(a).separation_from(e.observe(b)).degrees

        f.step_days = step_days
        return f


def dedupe_extrema(times, values, eps_days: float = 0.5):
    """Collapse near-identical extremum times.

    find_minima/find_maxima can converge onto the same extremum from
    two adjacent samples and report it twice (seconds apart); keep the
    first of each cluster.
    """

    out = []
    for t, v in zip(times, values):
        if out and t.tt - out[-1][0].tt < eps_days:
            continue
        out.append((t, v))
    return out


@cache
def context() -> Context:
    return Context()
