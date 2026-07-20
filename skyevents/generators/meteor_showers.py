"""Meteor shower peaks from a static IMO working-list catalog.

The peak instant for a year is when the Sun's apparent ecliptic
longitude in the **J2000 equinox** frame crosses the catalog value:
IMO publishes peak solar longitudes for equinox J2000.0, and the
stage-0 calibration confirmed the feed does the same (of-date
longitudes would shift peaks by ~0.37 deg = ~9 hours).

Catalog longitudes were verified against the feed instants during the
stage-0 spike; ZHR values are from the IMO working list (indicative,
variable showers carry their typical value).

The shower slug is stored as the event's only "body" so that uids stay
unique when two showers peak on the same day (e.g. the Southern
delta-Aquariids and alpha-Capricornids, both around Jul 30).
"""

from skyfield.framelib import ecliptic_J2000_frame
from skyfield.searchlib import find_discrete

from skyevents.generators.base import context
from skyevents.model import Event, EventType

# slug, display name (en), peak solar longitude (deg, J2000), ZHR
SHOWERS = [
    ("quadrantids", "Quadrantids", 283.2, 110),
    ("gamma_ursae_minorids", "γ-Ursae Minorids", 299.0, 3),
    ("alpha_centaurids", "α-Centaurids", 319.2, 6),
    ("gamma_normids", "γ-Normids", 354.0, 6),
    ("lyrids", "Lyrids", 32.3, 18),
    ("pi_puppids", "π-Puppids", 33.5, 5),
    ("eta_aquariids", "η-Aquariids", 45.5, 50),
    ("eta_lyrids", "η-Lyrids", 48.0, 3),
    ("daytime_arietids", "Daytime Arietids", 79.6, 30),
    ("june_bootids", "June Bootids", 95.7, 5),
    ("piscis_austrinids", "Piscis Austrinids", 125.7, 5),
    ("southern_delta_aquariids", "Southern δ-Aquariids", 127.0, 25),
    ("alpha_capricornids", "α-Capricornids", 127.01, 5),
    ("perseids", "Perseids", 140.0, 100),
    ("kappa_cygnids", "κ-Cygnids", 145.0, 3),
    ("aurigids", "Aurigids", 158.6, 6),
    ("september_epsilon_perseids", "September ε-Perseids", 166.7, 5),
    ("daytime_sextantids", "Daytime Sextantids", 184.3, 5),
    ("october_camelopardalids", "October Camelopardalids", 192.6, 5),
    ("draconids", "Draconids", 195.4, 10),
    ("southern_taurids", "Southern Taurids", 197.0, 5),
    ("delta_aurigids", "δ-Aurigids", 198.0, 2),
    ("epsilon_geminids", "ε-Geminids", 205.0, 3),
    ("orionids", "Orionids", 208.0, 20),
    ("leonis_minorids", "Leonis Minorids", 211.0, 2),
    ("northern_taurids", "Northern Taurids", 230.0, 5),
    ("leonids", "Leonids", 235.3, 10),
    ("alpha_monocerotids", "α-Monocerotids", 239.3, 5),
    ("november_orionids", "November Orionids", 246.0, 3),
    ("phoenicids", "Phoenicids", 250.0, 3),
    ("december_phi_cassiopeids", "December φ-Cassiopeids", 254.0, 5),
    ("puppid_velids", "Puppid-Velids", 255.0, 10),
    ("monocerotids", "Monocerotids", 257.0, 2),
    ("sigma_hydrids", "σ-Hydrids", 260.0, 3),
    ("geminids", "Geminids", 262.2, 150),
    ("comae_berenicids", "Comae Berenicids", 264.0, 3),
    ("december_leonis_minorids", "December Leonis Minorids", 268.0, 5),
    ("ursids", "Ursids", 270.7, 10),
]


def generate(year: int) -> list[Event]:
    ctx = context()
    t0, t1 = ctx.search_window(year)

    def sun_lon(t):
        pos = ctx.earth.at(t).observe(ctx.sun).apparent()
        _, lon, _ = pos.frame_latlon(ecliptic_J2000_frame)
        return lon.degrees

    events = []
    for slug, name, peak_lon, zhr in SHOWERS:
        def past_peak(t, peak_lon=peak_lon):
            return ((sun_lon(t) - peak_lon + 180.0) % 360.0) - 180.0 > 0

        past_peak.step_days = 20.0
        times, crossings = find_discrete(t0, t1, past_peak)
        events += [
            Event.create(EventType.METEOR_SHOWER, t.utc_datetime(), [slug],
                         {"name": name, "zhr": zhr,
                          "solar_lon_deg": peak_lon})
            for t, rising in zip(times, crossings) if rising
        ]
    return sorted(events, key=lambda e: e.dt_utc)
