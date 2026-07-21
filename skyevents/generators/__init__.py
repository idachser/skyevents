"""Event generators, one module per event type"""

from skyevents.generators import (
    close_approaches,
    elongations,
    lunar_apsides,
    lunar_eclipses,
    meteor_showers,
    moon_phases,
    planet_sun,
    seasons,
    solar_eclipses,
    stations,
)
from skyevents.model import Event

# Bump to force cache regeneration when generator logic or thresholds
# change. Lives in the cache only — never in event uids, which must
# stay determined by the event identity alone.
GENERATOR_VERSION = 3

MODULES = (moon_phases, seasons, lunar_apsides, planet_sun, elongations,
           close_approaches, lunar_eclipses, solar_eclipses, meteor_showers,
           stations)


def generate_year(year: int) -> list[Event]:
    """All events of the year, every generator, sorted by time"""

    events = []
    for module in MODULES:
        events += module.generate(year)
    return sorted(events, key=lambda e: e.dt_utc)
