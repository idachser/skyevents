"""Comet events: perihelion, perigee, peak brightness.

The catalog is a small committed fixture (tests/data/CometEls.txt), a
handful of real MPC lines rather than the ~950-comet runtime download, so
the suite stays offline. Unlike the other generators there is no
in-the-sky.org reference from the stage-0 spike (comets were stage 7);
the anchors are instead the published magnitudes of a few bright comets
and the perihelion time, which must equal the T element exactly.
"""

from functools import cache

import pytest

from skyevents import comets
from skyevents.generators import comets as gen
from skyevents.model import EventType

from tests.util import assert_unique_uids

COMET_TYPES = {EventType.COMET_PERIHELION, EventType.COMET_PERIGEE,
               EventType.COMET_PEAK_BRIGHTNESS}


@cache
def generate(year: int):
    return gen.generate(year)


def by_slug(events):
    out = {}
    for e in events:
        out.setdefault(e.bodies[0], {})[e.type] = e
    return out


def test_composition_2026():
    """The bright comets the fixture should surface, and only those.

    2P/Encke (perihelion 2027-02) and 460P (magnitude ~21) are in the
    fixture precisely to be left out -- Encke because its brightening is
    still climbing at the year's edge, 460P because it never nears the
    cut.
    """

    events = generate(2026)
    slugs = {e.bodies[0] for e in events}

    assert slugs == {"10p_tempel", "24p_schaumasse", "c_2024_e1_wierzchos",
                     "141p_machholz", "141p_a_machholz", "141p_d_machholz"}
    assert "2p_encke" not in slugs, "boundary artifact leaked into the year"
    assert "460p_panstarrs" not in slugs, "object below the cut published"

    assert all(e.type in COMET_TYPES for e in events)
    assert_unique_uids(events)
    assert events == sorted(events, key=lambda e: e.dt_utc)


def _comet(**overrides):
    fields = dict(
        designation="X", slug="x", magnitude_g=20.0, slope_k=4.0,
        perihelion_year=2026, perihelion_month=1, perihelion_day=1.0,
        perihelion_distance_au=0.5, eccentricity=1.0,
        argument_of_perihelion_deg=0.0, longitude_of_ascending_node_deg=0.0,
        inclination_deg=0.0)
    fields.update(overrides)
    return comets.Comet(**fields)


def test_prefilter_never_prunes_a_possible_earth_crosser():
    """q <= 1 comets can cross Earth's orbit, so no magnitude floor holds.

    A faint (g = 20) comet that passes close to Earth can still turn
    bright, so it must be searched rather than pruned on its perihelion
    distance -- the floor would otherwise silently drop it.
    """

    from math import isinf

    assert isinf(gen._brightest_possible(_comet(perihelion_distance_au=0.5)))
    # a distant comet stays boundable and prunable
    floor = gen._brightest_possible(_comet(perihelion_distance_au=3.0))
    assert floor > gen.MAX_MAGNITUDE


def test_peak_events_are_under_the_cut_and_every_comet_qualifies():
    """The peak-brightness event names the brightest instant, so it must
    beat the cut; perihelion and perigee events for a qualifying comet
    may be fainter, but each published comet clears the cut somewhere.
    """

    for slug, types in by_slug(generate(2026)).items():
        peak = types.get(EventType.COMET_PEAK_BRIGHTNESS)
        if peak is not None:
            assert peak.params["magnitude"] < gen.MAX_MAGNITUDE
        brightest = min(e.params["magnitude"] for e in types.values())
        assert brightest < gen.MAX_MAGNITUDE, f"{slug} never beats the cut"


def test_known_magnitudes():
    """Published peak magnitudes for a few of the fixture's comets."""

    peaks = {slug: types[EventType.COMET_PEAK_BRIGHTNESS]
             for slug, types in by_slug(generate(2026)).items()}

    for slug, expected in [("c_2024_e1_wierzchos", 5.1), ("10p_tempel", 6.9),
                           ("24p_schaumasse", 7.9)]:
        magnitude = peaks[slug].params["magnitude"]
        assert abs(magnitude - expected) <= 0.5, (
            f"{slug} peak magnitude {magnitude}, expected ~{expected}")


def test_perihelion_matches_the_element():
    """The perihelion instant is the T element, not a search result.

    So it must reproduce ts.tt(year, month, day) to the second -- the
    only slack is TT->UTC. This is the tightest correctness check the
    comet generator has.
    """

    ts = gen.context().ts
    catalog = {c.slug: c for c in comets.load_catalog()}

    for slug, types in by_slug(generate(2026)).items():
        comet = catalog[slug]
        expected = ts.tt(comet.perihelion_year, comet.perihelion_month,
                         comet.perihelion_day).utc_datetime()
        got = types[EventType.COMET_PERIHELION].dt_utc
        assert abs((got - expected).total_seconds()) < 2, (
            f"{slug} perihelion {got} vs element T {expected}")


def test_perigee_and_peak_can_share_a_date_without_colliding():
    """10P/Tempel's perigee and brightness peak fall on the same day.

    A single event type with a `kind` would give them the same
    date-only uid and collapse them; three distinct types keep them
    apart. This is why comets are not one type with a discriminant.
    """

    tempel = by_slug(generate(2026))["10p_tempel"]
    assert set(tempel) == COMET_TYPES

    perigee = tempel[EventType.COMET_PERIGEE]
    peak = tempel[EventType.COMET_PEAK_BRIGHTNESS]
    assert perigee.dt_utc.date() == peak.dt_utc.date()
    assert perigee.uid != peak.uid


def test_split_comet_fragments_get_distinct_slugs():
    """141P, 141P-A and 141P-D share a packed designation (0141P).

    The slug comes from the readable designation, which carries the
    fragment letter, so the three do not share a uid.
    """

    slugs = {e.bodies[0] for e in generate(2026)}
    fragments = {"141p_machholz", "141p_a_machholz", "141p_d_machholz"}
    assert fragments <= slugs
    assert len(fragments) == 3


def test_params_carry_what_the_texts_read():
    peak = by_slug(generate(2026))["10p_tempel"][
        EventType.COMET_PEAK_BRIGHTNESS]
    assert peak.params["name"] == "10P/Tempel"
    assert peak.params["magnitude"] < gen.MAX_MAGNITUDE
    assert 0.0 < peak.params["distance_au"] < 5.0
    assert 0.0 < peak.params["heliocentric_au"] < 5.0


# --- parsing -------------------------------------------------------------

FIXTURE_ROWS = [line for line in comets.catalog_path().read_text(
    encoding="latin-1").splitlines() if not line.startswith("#")]


def test_parse_reads_the_columns():
    tempel = next(c for c in comets.parse(FIXTURE_ROWS)
                  if c.designation == "10P/Tempel")

    assert tempel.slug == "10p_tempel"
    assert tempel.perihelion_year == 2026 and tempel.perihelion_month == 8
    assert abs(tempel.perihelion_day - 2.1148) < 1e-4
    assert abs(tempel.perihelion_distance_au - 1.417738) < 1e-6
    assert abs(tempel.eccentricity - 0.537453) < 1e-6
    assert abs(tempel.magnitude_g - 5.0) < 1e-6
    assert abs(tempel.slope_k - 10.0) < 1e-6


def test_bad_rows_are_skipped_not_raised():
    """One unparsable row costs its comet, not the whole background pass."""

    good = FIXTURE_ROWS[:2]

    assert len(comets.parse(good + ["garbage"])) == 2
    # truncated mid-line: the element columns are gone, so it must not
    # parse into a chopped record
    assert len(comets.parse(good + [good[0][:60]])) == 2
    # a blank magnitude column cannot be ranked
    blanked = good[0][:90] + "     " + good[0][95:]
    assert len(comets.parse(good + [blanked])) == 2


def test_missing_catalog_is_empty_not_an_error(tmp_path, monkeypatch):
    """No download yet is a normal state: no comet events, logged.

    Contrast the asteroid catalog, whose emptiness is a broken deploy --
    that one is committed and must always be there.
    """

    monkeypatch.setattr(comets, "catalog_path",
                        lambda: tmp_path / "CometEls.txt")
    assert comets.load_catalog() == []


# --- runtime refresh -----------------------------------------------------

class FakeResponse:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_refresh_is_throttled(tmp_path, monkeypatch):
    """A recent local copy is not re-downloaded."""

    path = tmp_path / "CometEls.txt"
    path.write_bytes(b"x" * comets.MIN_DOWNLOAD_BYTES)
    monkeypatch.setattr(comets, "catalog_path", lambda: path)

    def boom(*a, **k):
        raise AssertionError("must not download when the copy is fresh")

    monkeypatch.setattr(comets.urllib.request, "urlopen", boom)
    assert comets.refresh_catalog() is False


# a real, parseable body large enough to clear both the size floor and
# the comet-count floor (the fixture rows, repeated)
VALID_DOWNLOAD = (("\n".join(FIXTURE_ROWS) + "\n") * 40).encode("latin-1")


def test_refresh_downloads_and_replaces(tmp_path, monkeypatch):
    path = tmp_path / "CometEls.txt"
    monkeypatch.setattr(comets, "catalog_path", lambda: path)
    assert len(VALID_DOWNLOAD) >= comets.MIN_DOWNLOAD_BYTES
    monkeypatch.setattr(comets.urllib.request, "urlopen",
                        lambda *a, **k: FakeResponse(VALID_DOWNLOAD))

    assert comets.refresh_catalog() is True
    assert path.read_bytes() == VALID_DOWNLOAD


def test_refresh_refuses_a_short_download(tmp_path, monkeypatch):
    """A truncated download leaves the previous catalog untouched."""

    path = tmp_path / "CometEls.txt"
    path.write_bytes(b"previous catalog")
    monkeypatch.setattr(comets, "catalog_path", lambda: path)
    monkeypatch.setattr(comets.urllib.request, "urlopen",
                        lambda *a, **k: FakeResponse(b"too short"))

    with pytest.raises(ValueError):
        comets.refresh_catalog(force=True)
    assert path.read_bytes() == b"previous catalog"


def test_refresh_rejects_a_non_catalog_body(tmp_path, monkeypatch):
    """A large but bogus body (an HTML error page) must not overwrite.

    It clears the byte-size floor yet parses to no comets; the previous
    catalog has to survive, or a CDN hiccup would blank comet coverage
    for a week (refresh is throttled).
    """

    path = tmp_path / "CometEls.txt"
    path.write_bytes(b"previous catalog")
    monkeypatch.setattr(comets, "catalog_path", lambda: path)
    html = b"<html><body>403 Forbidden</body></html>\n" * 4000
    assert len(html) >= comets.MIN_DOWNLOAD_BYTES
    monkeypatch.setattr(comets.urllib.request, "urlopen",
                        lambda *a, **k: FakeResponse(html))

    with pytest.raises(ValueError):
        comets.refresh_catalog(force=True)
    assert path.read_bytes() == b"previous catalog"
