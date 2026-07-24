"""Comet orbital elements in the Minor Planet Center's CometEls.txt format.

Positions come from two-body Kepler propagation of the elements, exactly
as `skyfield.data.mpc.comet_orbit` builds them (that module imports
pandas at import time for a fixed-width read; we need a handful of
columns from a few hundred lines, so the columns are sliced here). That
means the private `_KeplerOrbit`: skyfield is pinned in the lockfile, and
the comet tests fail loudly if an upgrade ever changes it.

Unlike the asteroid catalog (committed, numbered objects with stable
elements), CometEls.txt is **downloaded at runtime** into SKYEVENTS_DATA
by the API's background loop and refreshed at most weekly: the comet list
turns over constantly as objects are discovered and orbits refined, and a
year already generated must be able to pick up a comet found afterwards.
The generator only ever reads the local file, so the tests stay offline
(a few-line fixture in tests/data/). No file yet -> no comet events, and
that is logged rather than raised: an absent download is a normal state
(offline, or the first minutes after startup), not a broken deploy.
"""

import logging
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data.spice import inertial_frames
from skyfield.keplerlib import _KeplerOrbit

from skyevents.ephemeris import data_dir
from skyevents.mpc import slugify

COMETELS_URL = "https://www.minorplanetcenter.net/iau/MPCORB/CometEls.txt"
CATALOG_NAME = "CometEls.txt"

# Refresh no more often than this: the file changes daily upstream, but
# a week keeps comet coverage current without hammering the MPC.
REFRESH_INTERVAL_S = 7 * 24 * 3600

# A download smaller than this did not really work (the file is ~160 KB,
# ~950 comets); keep the old copy rather than overwrite it with a stub.
MIN_DOWNLOAD_BYTES = 50_000

# ...and a body that is the right size but parses to far too few comets
# is not the catalog either -- an HTML error page, a captive portal, a
# CDN block. Validate the content, not just the length, before replacing
# a good file. The real catalog holds ~950.
MIN_COMETS = 200

# The MPC's CDN answers a default urllib User-Agent with a 403 HTML page,
# which is exactly the large-but-bogus body MIN_COMETS guards against;
# identify ourselves so we get the file.
USER_AGENT = "skyevents comet-catalog fetcher"

logger = logging.getLogger("skyevents")


@dataclass(frozen=True)
class Comet:
    """One CometEls.txt line: the elements plus what the texts need"""

    designation: str
    slug: str
    magnitude_g: float
    slope_k: float
    perihelion_year: int
    perihelion_month: int
    perihelion_day: float
    perihelion_distance_au: float
    eccentricity: float
    argument_of_perihelion_deg: float
    longitude_of_ascending_node_deg: float
    inclination_deg: float


def catalog_path() -> Path:
    return Path(data_dir()) / CATALOG_NAME


def parse(lines) -> list[Comet]:
    """Parse CometEls.txt lines; blank and '#' comment lines are skipped.

    An unparsable line is skipped with a warning rather than raised on,
    for the same reason as the asteroid catalog: the generators run one
    after another in a single background pass, and one bad row must not
    cost the whole year. An empty result is the caller's to judge -- for
    comets it is a normal "no local catalog", not an error.
    """

    comets, skipped = [], []
    for line in lines:
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        designation = line[102:158].strip()
        try:
            if not designation:
                raise ValueError("no designation")
            fields = _elements(line)
        except ValueError:
            skipped.append(line[:12])
            continue
        comets.append(Comet(
            designation=designation, slug=slugify(designation), **fields))
    if skipped:
        logger.warning("comet catalog: skipped %d unparsable line(s): %s",
                       len(skipped), skipped[:3])
    return comets


def _elements(line: str) -> dict:
    """The CometEls.txt columns we read; ValueError if any is blank.

    Fixed-width layout (1-indexed in the MPC spec): perihelion time T in
    columns 15-29, q 31-39, e 41-49, argument of perihelion 51-59, node
    61-69, inclination 71-79, absolute magnitude 92-95, slope 97-100.
    """

    return dict(
        magnitude_g=float(line[90:95]),
        slope_k=float(line[96:100]),
        perihelion_year=int(line[14:18]),
        perihelion_month=int(line[19:21]),
        perihelion_day=float(line[22:29]),
        perihelion_distance_au=float(line[30:39]),
        eccentricity=float(line[40:49]),
        argument_of_perihelion_deg=float(line[50:59]),
        longitude_of_ascending_node_deg=float(line[60:69]),
        inclination_deg=float(line[70:79]),
    )


def load_catalog() -> list[Comet]:
    """Parse the local CometEls.txt, or [] (logged) if it is not there.

    The file arrives by runtime download; an absent one means offline or
    a fresh start, not a fault -- unlike the committed asteroid catalog,
    whose emptiness is a broken deploy.
    """

    path = catalog_path()
    if not path.exists():
        logger.warning("no comet catalog at %s: comet events skipped "
                       "(the background loop downloads it)", path)
        return []
    # latin-1, not ascii: MPCORB-family files are ascii, but one stray
    # byte in a comet name must not take a whole year's generation down
    with path.open(encoding="latin-1") as lines:
        return parse(lines)


def orbit(comet: Comet, ts):
    """Heliocentric Kepler orbit; add a Sun to observe it.

    `sun + orbit(comet, ts)` behaves like any other ephemeris body. Built
    from the periapsis, so eccentric, parabolic (e = 1) and hyperbolic
    (e > 1) comets are all handled, unlike the asteroids' mean-anomaly
    form.
    """

    e = comet.eccentricity
    # semilatus rectum: p = a(1 - e^2) = q(1 + e) for e != 1, and 2q at
    # the parabolic limit -- exactly as skyfield.data.mpc.comet_orbit
    semilatus_rectum = (comet.perihelion_distance_au * 2.0 if e == 1.0
                        else comet.perihelion_distance_au * (1.0 + e))
    t_perihelion = ts.tt(comet.perihelion_year, comet.perihelion_month,
                         comet.perihelion_day)
    kepler = _KeplerOrbit._from_periapsis(
        semilatus_rectum,
        e,
        comet.inclination_deg,
        comet.longitude_of_ascending_node_deg,
        comet.argument_of_perihelion_deg,
        t_perihelion,
        GM_SUN,
        10,
        comet.designation,
    )
    # elements are referred to the J2000 ecliptic, positions to the
    # J2000 equator -- the rotation comet_orbit applies
    kepler._rotation = inertial_frames["ECLIPJ2000"].T
    return kepler


def refresh_catalog(force: bool = False) -> bool:
    """Download CometEls.txt into SKYEVENTS_DATA if it is due a refresh.

    Returns True if it fetched a new copy, False if the local one was
    still fresh. Raises on a network or short-read failure so the caller
    can log it and keep running on the previous copy -- the write is
    atomic, so a failed download never leaves a truncated catalog behind.
    """

    path = catalog_path()
    if (not force and path.exists()
            and time.time() - path.stat().st_mtime < REFRESH_INTERVAL_S):
        return False
    request = urllib.request.Request(
        COMETELS_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as resp:
        data = resp.read()
    if len(data) < MIN_DOWNLOAD_BYTES:
        raise ValueError(
            f"CometEls.txt download was only {len(data)} bytes "
            f"(expected >= {MIN_DOWNLOAD_BYTES}); keeping the old copy")
    parsed = parse(data.decode("latin-1").splitlines())
    if len(parsed) < MIN_COMETS:
        raise ValueError(
            f"CometEls.txt download parsed to only {len(parsed)} comets "
            f"(expected >= {MIN_COMETS}); it is probably not the catalog "
            f"(an error page?) -- keeping the old copy")
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_name(path.name + ".new")
    scratch.write_bytes(data)
    scratch.replace(path)
    logger.info("refreshed comet catalog: %d bytes at %s", len(data), path)
    return True
