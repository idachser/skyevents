"""Shared machinery for the per-type event generators.

All computations are geocentric, matching the in-the-sky.org feed the
stage-0 spike was calibrated against.
"""

from functools import cache

from skyevents.ephemeris import load_ephemeris, load_timescale

PLANETS = ("mercury", "venus", "mars", "jupiter", "saturn",
           "uranus", "neptune")


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

    def body(self, name):
        if name == "sun":
            return self.sun
        if name == "moon":
            return self.moon
        return self.planets[name]

    def year_window(self, year: int):
        """Half-open [Jan 1 UTC, Jan 1 UTC of the next year)"""

        return self.ts.utc(year, 1, 1), self.ts.utc(year + 1, 1, 1)

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
