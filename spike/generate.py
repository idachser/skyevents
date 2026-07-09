"""Skyfield prototypes of the stage-2 generators (spike quality).

Everything is geocentric, like the feed. Each function returns Rec
lists; diff.py compares them with the parsed feed.
"""

from math import asin, degrees

from skyfield import almanac, eclipselib
from skyfield.framelib import ecliptic_frame
from skyfield.searchlib import find_discrete, find_maxima, find_minima

from skyevents.ephemeris import load_ephemeris, load_timescale
from spike.records import PLANETS, Rec, canonical

R_SUN_KM = 696340.0
R_MOON_KM = 1737.4
R_EARTH_KM = 6378.14

MOON_PLANET_MAX_DEG = 7.0   # feed uses maxdiff=7 for Moon pairs
PLANET_PLANET_MAX_DEG = 2.5

PHASE_NAMES = ("new", "first_quarter", "full", "last_quarter")
SEASON_NAMES = ("march_equinox", "june_solstice",
                "september_equinox", "december_solstice")

# IMO working-list peak solar longitudes (deg, equinox of date);
# names as they appear in the feed. Values from memory — validating
# them against the feed is part of the point of this spike.
SHOWERS = {
    "Quadrantid": 283.16,
    "Lyrid": 32.32,
    "η-Aquariid": 45.5,
    "Southern δ-Aquariid": 126.9,
    "α-Capricornid": 127.0,
    "Perseid": 140.0,
    "Aurigid": 158.6,
    "September ε-Perseid": 166.7,
    "Draconid": 195.4,
    "Orionid": 208.0,
    "Southern Taurid": 223.0,
    "Northern Taurid": 230.0,
    "Leonid": 235.27,
    "Geminid": 262.2,
    "Ursid": 270.7,
}


class Spike:
    def __init__(self):
        self.eph = load_ephemeris()
        self.ts = load_timescale()
        self.earth = self.eph["earth"]
        self.sun = self.eph["sun"]
        self.moon = self.eph["moon"]
        self.planet = {
            name: self.eph[name if name in ("mercury", "venus")
                           else f"{name} barycenter"]
            for name in PLANETS
        }

    def target(self, name):
        return {"sun": self.sun, "moon": self.moon}.get(
            name, self.planet.get(name))

    def _separation(self, a, b, step_days):
        earth = self.earth

        def f(t):
            e = earth.at(t)
            return e.observe(a).separation_from(e.observe(b)).degrees

        f.step_days = step_days
        return f

    def _ecliptic_lon(self, t, body):
        pos = self.earth.at(t).observe(body).apparent()
        _, lon, _ = pos.frame_latlon(ecliptic_frame)
        return lon.degrees

    # -- generators ----------------------------------------------------

    def moon_phases(self, t0, t1):
        t, y = find_discrete(t0, t1, almanac.moon_phases(self.eph))
        return [Rec("moon_phase", ("moon",), ti.utc_datetime(),
                    PHASE_NAMES[yi]) for ti, yi in zip(t, y)]

    def seasons(self, t0, t1):
        t, y = find_discrete(t0, t1, almanac.seasons(self.eph))
        return [Rec("season", ("sun",), ti.utc_datetime(),
                    SEASON_NAMES[yi]) for ti, yi in zip(t, y)]

    def lunar_apsides(self, t0, t1):
        def dist(t):
            return self.earth.at(t).observe(self.moon).distance().km

        dist.step_days = 5.0
        events = []
        for finder, kind in ((find_maxima, "apogee"),
                             (find_minima, "perigee")):
            t, v = finder(t0, t1, dist)
            events += [Rec("lunar_apsis", ("moon",), ti.utc_datetime(),
                           kind, extra={"distance_km": float(vi)})
                       for ti, vi in zip(t, v)]
        return events

    def planet_sun(self, t0, t1):
        events = []
        for name in PLANETS:
            f = almanac.oppositions_conjunctions(
                self.eph, self.planet[name])
            t, y = find_discrete(t0, t1, f)
            for ti, yi in zip(t, y):
                if name in ("mercury", "venus"):
                    e = self.earth.at(ti)
                    d_planet = e.observe(self.planet[name]).distance().km
                    d_sun = e.observe(self.sun).distance().km
                    kind = "inferior" if d_planet < d_sun else "superior"
                else:
                    kind = "opposition" if yi else "conjunction"
                events.append(
                    Rec("planet_sun", (name,), ti.utc_datetime(), kind))
        return events

    def elongations(self, t0, t1):
        events = []
        for name in ("mercury", "venus"):
            f = self._separation(self.planet[name], self.sun, 5.0)
            t, v = find_maxima(t0, t1, f)
            for ti, vi in zip(t, v):
                lon_p = self._ecliptic_lon(ti, self.planet[name])
                lon_s = self._ecliptic_lon(ti, self.sun)
                side = "east" if (lon_p - lon_s) % 360 < 180 else "west"
                events.append(
                    Rec("elongation", (name,), ti.utc_datetime(), side,
                        extra={"elongation_deg": float(vi)}))
        return events

    def close_approaches(self, t0, t1):
        pairs = [(("moon", p), MOON_PLANET_MAX_DEG, 2.0) for p in PLANETS]
        for i, a in enumerate(PLANETS):
            for b in PLANETS[i + 1:]:
                pairs.append(((a, b), PLANET_PLANET_MAX_DEG, 5.0))

        events = []
        for (a, b), threshold, step in pairs:
            f = self._separation(self.target(a), self.target(b), step)
            t, v = find_minima(t0, t1, f)
            for ti, vi in zip(t, v):
                if vi < threshold:
                    events.append(Rec(
                        "close_approach", canonical((a, b)),
                        ti.utc_datetime(),
                        extra={"separation_deg": float(vi)}))
        return events

    def lunar_eclipses(self, t0, t1):
        t, y, _ = eclipselib.lunar_eclipses(t0, t1, self.eph)
        kinds = ("penumbral", "partial", "total")
        return [Rec("lunar_eclipse", ("moon",), ti.utc_datetime(),
                    kinds[yi]) for ti, yi in zip(t, y)]

    def solar_eclipses(self, t0, t1):
        t, y = find_discrete(t0, t1, almanac.moon_phases(self.eph))
        new_moons = [ti for ti, yi in zip(t, y) if yi == 0]

        sep = self._separation(self.sun, self.moon, 0.05)
        events = []
        for tn in new_moons:
            window = self.ts.tt_jd([tn.tt - 1.5, tn.tt + 1.5])
            tmin, vmin = find_minima(window[0], window[1], sep)
            if len(tmin) == 0:
                continue
            ti, si = tmin[0], float(vmin[0])

            e = self.earth.at(ti)
            d_sun = e.observe(self.sun).distance().km
            d_moon = e.observe(self.moon).distance().km
            r_sun = degrees(asin(R_SUN_KM / d_sun))
            r_moon = degrees(asin(R_MOON_KM / d_moon))
            parallax = degrees(asin(R_EARTH_KM / d_moon))

            if si >= r_sun + r_moon + parallax:
                continue
            # rough geocentric classification; hybrids will misreport
            if si < parallax:
                r_moon_topo = degrees(asin(R_MOON_KM / (d_moon - R_EARTH_KM)))
                kind = "total" if r_moon_topo >= r_sun else "annular"
            else:
                kind = "partial"
            events.append(Rec(
                "solar_eclipse", ("sun", "moon"), ti.utc_datetime(), kind,
                extra={"separation_deg": si,
                       "radii_plus_parallax": r_sun + r_moon + parallax}))
        return events

    def meteor_showers(self, t0, t1):
        events = []
        for name, target_lon in SHOWERS.items():
            def f(t, target_lon=target_lon):
                lon = self._ecliptic_lon(t, self.sun)
                return ((lon - target_lon + 180.0) % 360.0) - 180.0 > 0

            f.step_days = 20.0
            t, y = find_discrete(t0, t1, f)
            events += [Rec("meteor_shower", (), ti.utc_datetime(), name)
                       for ti, yi in zip(t, y) if yi]
        return events

    def all_events(self, t0, t1):
        events = []
        for gen in (self.moon_phases, self.seasons, self.lunar_apsides,
                    self.planet_sun, self.elongations,
                    self.close_approaches, self.lunar_eclipses,
                    self.solar_eclipses, self.meteor_showers):
            events += gen(t0, t1)
        return sorted(events, key=lambda r: r.dt)
