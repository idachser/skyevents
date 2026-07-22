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

Run as a module (`python -m skyevents.mpc <path>`), this filters
MPCORB.DAT on stdin down to the committed catalog; see README.md for
the full pipe.
"""

import logging
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data.spice import inertial_frames
from skyfield.keplerlib import _KeplerOrbit

MPCORB_URL = "https://www.minorplanetcenter.net/iau/MPCORB/MPCORB.DAT"

# Catalog cut: an object of H = 8.6 barely reaches magnitude 10 at its
# best opposition, so everything the generator can publish is inside.
MAX_H = 8.6

# A refresh that yields fewer rows than this did not really work: the
# download was cut short, or the columns moved. Today's catalog holds
# 242, and the count only grows as MPC refines magnitudes.
MIN_CATALOG_SIZE = 200

# The last column we read ends at 194; a line shorter than that has
# been truncated (a range request cuts the file mid-line) and would
# parse into a chopped name -- a different slug, a different uid.
LINE_LENGTH = 194

DESIGNATION_RE = re.compile(r"\((\d+)\)\s+(.+)")

logger = logging.getLogger("skyevents")


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
    """Parse MPCORB lines; blank and '#' comment lines are skipped.

    An unparsable line is skipped with a warning rather than raised on:
    generators run one after another inside a single background pass,
    so a hard failure here would cost the whole year -- eclipses, moon
    phases and all -- over one bad row. Wholesale failure still has to
    be loud, and that is the caller's business (see the generator,
    which refuses an empty catalog).
    """

    planets, skipped = [], []
    for line in lines:
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        match = (DESIGNATION_RE.match(line[166:194].strip())
                 if len(line) >= LINE_LENGTH else None)
        if match is None:
            skipped.append(line[:20])
            continue
        number, name = int(match.group(1)), match.group(2)
        try:
            fields = _elements(line)
        except ValueError:
            skipped.append(line[:20])
            continue
        planets.append(MinorPlanet(
            number=number, name=name, slug=slugify(name), **fields))
    if skipped:
        logger.warning("minor planet catalog: skipped %d unparsable line(s): "
                       "%s", len(skipped), skipped[:3])
    return planets


def _elements(line: str) -> dict:
    """The MPCORB columns we read; ValueError if any of them is blank"""

    return dict(
        magnitude_h=float(line[8:13]),
        slope_g=float(line[14:19]),
        epoch=unpack_epoch(line[20:25]),
        mean_anomaly_deg=float(line[26:35]),
        argument_of_perihelion_deg=float(line[37:46]),
        longitude_of_ascending_node_deg=float(line[48:57]),
        inclination_deg=float(line[59:68]),
        eccentricity=float(line[70:79]),
        semimajor_axis_au=float(line[92:103]),
    )


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


def select(lines) -> list[str]:
    """The catalog rows among MPCORB lines: numbered, H <= MAX_H"""

    kept = []
    for line in lines:
        line = line.rstrip("\n")
        if len(line) < LINE_LENGTH or not line[:5].isdigit():
            continue
        try:
            magnitude_h = float(line[8:13])
        except ValueError:
            # MPCORB leaves H blank for objects without a measured
            # magnitude; the generator could not rank them anyway
            continue
        if magnitude_h <= MAX_H:
            kept.append(line)
    return kept


def render_catalog(kept: list[str]) -> str:
    """The catalog file: a provenance header, then the rows"""

    header = f"""\
# Orbital elements in MPCORB format: the {len(kept)} numbered minor
# planets with H <= {MAX_H} among numbers {int(kept[0][:5])}-{int(kept[-1][:5])}
# -- the prefix of MPCORB.DAT that the pipe in README.md downloads.
# Every object that can reach magnitude 10, the generator's publication
# cut, is a low-numbered main-belt asteroid; out beyond Jupiter it
# would take H < 2 to get there.
# Source: {MPCORB_URL}
# (Minor Planet Center), elements for epoch {unpack_epoch(kept[0][20:25])}.
# Regenerate: see README.md.
"""
    return header + "".join(line + "\n" for line in kept)


def _main(args: list[str]) -> None:
    """Rewrite the catalog from MPCORB rows on stdin.

    The destination is an argument, not a shell redirect: `> file`
    truncates the committed catalog before this even runs, so a
    download that fails or arrives truncated would destroy it. Here a
    short read aborts and leaves the old file in place.
    """

    kept = select(sys.stdin)
    if len(kept) < MIN_CATALOG_SIZE:
        raise SystemExit(
            f"only {len(kept)} usable MPCORB rows on stdin, expected at "
            f"least {MIN_CATALOG_SIZE}: the download was cut short or the "
            f"columns moved. Catalog left unchanged.")
    text = render_catalog(kept)
    if not args:
        sys.stdout.write(text)
        return
    path = Path(args[0])
    # write beside the target and rename: an interrupted write must not
    # leave a half-catalog behind either
    scratch = path.with_name(path.name + ".new")
    scratch.write_text(text, encoding="latin-1")
    scratch.replace(path)
    print(f"{path}: {len(kept)} objects, epoch "
          f"{unpack_epoch(kept[0][20:25])}", file=sys.stderr)


if __name__ == "__main__":
    _main(sys.argv[1:])
