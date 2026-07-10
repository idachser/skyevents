from skyevents.generators import meteor_showers
from skyevents.model import EventType

from tests.util import assert_matches_reference, assert_unique_uids

# all 2026 peaks from the in-the-sky.org feed (stage-0 spike capture).
# The tight tolerance is deliberate: computing the crossing in the
# of-date instead of the J2000 ecliptic frame would shift every peak
# by ~9 hours, and this must fail loudly.
REFERENCE = [
    ("2026-01-03 22:35", "quadrantids"),
    ("2026-01-19 10:49", "gamma_ursae_minorids"),
    ("2026-02-08 08:13", "alpha_centaurids"),
    ("2026-03-14 23:00", "gamma_normids"),
    ("2026-04-22 19:17", "lyrids"),
    ("2026-04-24 00:49", "pi_puppids"),
    ("2026-05-06 09:22", "eta_aquariids"),
    ("2026-05-08 23:23", "eta_lyrids"),
    ("2026-06-10 20:31", "daytime_arietids"),
    ("2026-06-27 17:12", "june_bootids"),
    ("2026-07-29 03:51", "piscis_austrinids"),
    ("2026-07-30 12:29", "southern_delta_aquariids"),
    ("2026-07-30 12:44", "alpha_capricornids"),
    ("2026-08-13 02:09", "perseids"),
    ("2026-08-18 07:01", "kappa_cygnids"),
    ("2026-09-01 09:29", "aurigids"),
    ("2026-09-09 17:59", "september_epsilon_perseids"),
    ("2026-09-27 18:41", "daytime_sextantids"),
    ("2026-10-06 05:16", "october_camelopardalids"),
    ("2026-10-09 01:22", "draconids"),
    ("2026-10-10 16:13", "southern_taurids"),
    ("2026-10-11 16:30", "delta_aurigids"),
    ("2026-10-18 18:00", "epsilon_geminids"),
    ("2026-10-21 18:28", "orionids"),
    ("2026-10-24 18:50", "leonis_minorids"),
    ("2026-11-12 18:18", "northern_taurids"),
    ("2026-11-18 00:35", "leonids"),
    ("2026-11-21 23:45", "alpha_monocerotids"),
    ("2026-11-28 14:49", "november_orionids"),
    ("2026-12-02 13:35", "phoenicids"),
    ("2026-12-06 12:12", "december_phi_cassiopeids"),
    ("2026-12-07 11:50", "puppid_velids"),
    ("2026-12-09 11:05", "monocerotids"),
    ("2026-12-12 09:55", "sigma_hydrids"),
    ("2026-12-14 13:50", "geminids"),
    ("2026-12-16 08:18", "comae_berenicids"),
    ("2026-12-20 06:38", "december_leonis_minorids"),
    ("2026-12-22 22:18", "ursids"),
]

TOL_MINUTES = 60


def test_2026_matches_feed_reference():
    events = meteor_showers.generate(2026)

    def check(slug):
        def _check(event):
            assert event.type == EventType.METEOR_SHOWER
            assert event.bodies == [slug]
            assert event.params["zhr"] > 0
            assert event.params["name"]
        return _check

    assert_matches_reference(
        events, [(dt, check(slug)) for dt, slug in REFERENCE],
        TOL_MINUTES)
    assert_unique_uids(events)
