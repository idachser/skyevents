"""Minor-planet orbital elements in the Minor Planet Center's MPCORB format.

Positions come from two-body Kepler propagation of the elements, not
from an integrated ephemeris: good to arcminutes for main-belt objects
within a couple of years of the elements' epoch, which is all the
opposition search needs (its instant is soft anyway — the elongation
maximum is flat). The catalog therefore has to be refreshed
occasionally; tests/test_asteroids.py fails once its epoch grows stale.

Skyfield parses this format too, but `skyfield.data.mpc` imports pandas
at module level for a fixed-width read; we need eleven columns from a
few hundred lines, so the columns are sliced here and the orbit is
built exactly as `mpc.mpcorb_orbit` builds it. That means the private
`_KeplerOrbit`: skyfield is pinned in the lockfile, and the reference
oppositions in the tests fail loudly if an upgrade ever changes it.

Run as a module (`python -m skyevents.mpc`), this filters MPCORB.DAT on
stdin down to the committed catalog; see README.md for the full pipe.
"""

import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date

from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data.spice import inertial_frames
from skyfield.keplerlib import _KeplerOrbit

MPCORB_URL = "https://www.minorplanetcenter.net/iau/MPCORB/MPCORB.DAT"

# Catalog cut: an object of H = 8.6 barely reaches magnitude 10 at its
# best opposition, so everything the generator can publish is inside.
MAX_H = 8.6

DESIGNATION_RE = re.compile(r"\((\d+)\)\s+(.+)")


@dataclass(frozen=True)
class MinorPlanet:
    """One MPCORB line: the elements plus what the texts need"""

    number: int
    name: str
    slug: str
    magnitude_h: float
    slope_g: float
    epoch: date
    mean_anomaly_deg: float
    argument_of_perihelion_deg: float
    longitude_of_ascending_node_deg: float
    inclination_deg: float
    eccentricity: float
    semimajor_axis_au: float


def slugify(name: str) -> str:
    """Body slug for the uid: ascii, lowercase, non-alnum collapsed

    Numbered minor planets keep their names for good, so the slug is
    stable -- which is what the uid needs.
    """

    folded = unicodedata.normalize("NFKD", name).encode(
        "ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", folded.lower()).strip("_")


def unpack_epoch(packed: str) -> date:
    """MPC packed epoch ("K2669") to a date (2026-06-09)

    Century letter, two-digit year, then month and day in base 31 with
    digits running 1-9, A-V.
    """

    def digit(char: str) -> int:
        return ord(char) - (48 if char.isdigit() else 55)

    return date(100 * digit(packed[0]) + int(packed[1:3]),
                digit(packed[3]), digit(packed[4]))


def parse(lines) -> list[MinorPlanet]:
    """Parse MPCORB lines; blank and '#' comment lines are skipped"""

    planets = []
    for line in lines:
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        match = DESIGNATION_RE.match(line[166:194].strip())
        if match is None:
            raise ValueError(f"not a numbered minor planet: {line[:40]!r}")
        number, name = int(match.group(1)), match.group(2)
        planets.append(MinorPlanet(
            number=number,
            name=name,
            slug=slugify(name),
            magnitude_h=float(line[8:13]),
            slope_g=float(line[14:19]),
            epoch=unpack_epoch(line[20:25]),
            mean_anomaly_deg=float(line[26:35]),
            argument_of_perihelion_deg=float(line[37:46]),
            longitude_of_ascending_node_deg=float(line[48:57]),
            inclination_deg=float(line[59:68]),
            eccentricity=float(line[70:79]),
            semimajor_axis_au=float(line[92:103]),
        ))
    return planets


def orbit(planet: MinorPlanet, ts):
    """Heliocentric Kepler orbit; add a Sun to observe it

    `sun + orbit(planet, ts)` behaves like any other ephemeris body.
    """

    e = planet.eccentricity
    semilatus_rectum = planet.semimajor_axis_au * (1.0 - e * e)
    epoch = ts.tt(planet.epoch.year, planet.epoch.month, planet.epoch.day)
    kepler = _KeplerOrbit._from_mean_anomaly(
        semilatus_rectum,
        e,
        planet.inclination_deg,
        planet.longitude_of_ascending_node_deg,
        planet.argument_of_perihelion_deg,
        planet.mean_anomaly_deg,
        epoch,
        GM_SUN,
        10,
        planet.name,
    )
    # elements are referred to the J2000 ecliptic, positions to the
    # J2000 equator -- the rotation mpcorb_orbit applies
    kepler._rotation = inertial_frames["ECLIPJ2000"].T
    return kepler


def _write_catalog(lines, out) -> None:
    """Filter MPCORB lines down to the catalog; see README for the pipe"""

    kept = [line.rstrip("\n") for line in lines
            if len(line) > 190 and line[:5].isdigit()
            and float(line[8:13]) <= MAX_H]
    epoch = unpack_epoch(kept[0][20:25]) if kept else "?"
    print(f"# Orbital elements in MPCORB format: the {len(kept)} numbered\n"
          f"# minor planets with H <= {MAX_H} among numbers "
          f"{int(kept[0][:5])}-{int(kept[-1][:5])} -- the prefix of\n"
          f"# MPCORB.DAT that the pipe in README.md downloads. Every\n"
          f"# object that can reach magnitude 10, the generator's\n"
          f"# publication cut, is a low-numbered main-belt asteroid; out\n"
          f"# beyond Jupiter it would take H < 2 to get there.\n"
          f"# Source: {MPCORB_URL}\n"
          f"# (Minor Planet Center), elements for epoch {epoch}.\n"
          f"# Regenerate: see README.md.", file=out)
    for line in kept:
        print(line, file=out)


if __name__ == "__main__":
    _write_catalog(sys.stdin, sys.stdout)
