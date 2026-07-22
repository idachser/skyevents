"""Asteroid oppositions.

Reference: the "Asteroid N X at opposition" events of the
in-the-sky.org feed captured during the stage-0 spike, 2026 and 2027.
Our composition is a superset by design — the feed's own magnitude cut
sits within a tenth of ours, so borderline objects fall on either side
(see the generator docstring) — hence "covers the feed" rather than the
1:1 assert_matches_reference the other generators use.
"""

import io
from datetime import date, timedelta
from functools import cache

import pytest

from skyevents import mpc
from skyevents.generators import asteroids
from skyevents.model import EventType

from tests.util import assert_unique_uids, ref_dt

# (feed instant, slug). Feed times are quantized to a few minutes and
# it computes the elongation maximum as we do, so agreement is tight:
# the worst 2026/2027 case is 74 min.
FEED_2026 = [
    ("2026-01-02 14:22", "harmonia"),
    ("2026-01-23 19:10", "nysa"),
    ("2026-02-27 16:46", "iris"),
    ("2026-03-21 16:46", "massalia"),
    ("2026-05-28 23:58", "amphitrite"),
    ("2026-06-15 09:34", "irene"),
    ("2026-07-09 07:10", "melpomene"),
    ("2026-07-09 21:34", "flora"),
    ("2026-07-27 02:22", "juno"),
    ("2026-07-28 23:58", "bamberga"),
    ("2026-08-28 14:22", "metis"),
    ("2026-09-30 11:58", "nausikaa"),
    ("2026-10-04 14:22", "pallas"),
    ("2026-10-13 07:10", "vesta"),
]

FEED_2027 = [
    ("2027-01-07 17:51", "ceres"),
    ("2027-02-09 04:46", "euterpe"),
    ("2027-02-17 11:58", "hebe"),
    ("2027-03-04 16:46", "hygiea"),
    ("2027-05-18 09:34", "harmonia"),
    ("2027-05-25 16:46", "iris"),
    ("2027-06-10 02:22", "eunomia"),
    ("2027-07-01 09:34", "parthenope"),
    ("2027-09-21 07:10", "amphitrite"),
    ("2027-10-27 16:46", "fides"),
    ("2027-11-14 21:34", "kleopatra"),
    ("2027-12-01 11:58", "dembowska"),
    ("2027-12-06 11:58", "astraea"),
]

TOL_MINUTES = 180

# Ceres alone gets a wider one: the feed treats it as a dwarf planet,
# not an asteroid, and computes that family's opposition from ecliptic
# longitudes (as our planet_sun does) instead of from the elongation
# maximum. For an orbit inclined 10.6° the two are 7.7 h apart. Same
# event, different definition — see the generator docstring.
CERES_TOL_MINUTES = 9 * 60

# How far our extra objects may sit from the feed's cut: they exist
# because the two magnitude models disagree in the last tenth, and an
# extra object at, say, 8.5 would mean the feed dropped something
# genuinely bright and we have misunderstood its curation.
BORDERLINE_MAGNITUDE = 9.8

# Two-body propagation drifts as the elements age; the freshness test
# below is what keeps the tolerances above honest.
MAX_CATALOG_AGE_DAYS = 3 * 365

# real rows, for the parsing and refresh tests
CATALOG_ROWS = [line for line in asteroids.CATALOG.read_text(
    encoding="latin-1").splitlines() if not line.startswith("#")]


@cache
def generate(year: int):
    """Cached: a year of this generator is ~250 Kepler orbit searches"""

    return asteroids.generate(year)


def check_feed(events, reference):
    """Every feed event is ours, within tolerance; returns the extras"""

    by_slug = {}
    for event in events:
        assert event.type == EventType.ASTEROID_OPPOSITION
        assert len(event.bodies) == 1
        by_slug.setdefault(event.bodies[0], []).append(event)

    for text, slug in reference:
        assert slug in by_slug, f"{slug} missing: got {sorted(by_slug)}"
        assert len(by_slug[slug]) == 1, f"{slug} generated twice"
        event = by_slug[slug][0]
        tol = CERES_TOL_MINUTES if slug == "ceres" else TOL_MINUTES
        delta = abs((event.dt_utc - ref_dt(text)).total_seconds()) / 60
        assert delta <= tol, (
            f"{slug}: {event.dt_utc} vs feed {text} "
            f"({delta:.1f} min off, tolerance {tol})")

    return [by_slug[slug][0] for slug in
            set(by_slug) - {slug for _, slug in reference}]


@pytest.mark.parametrize("year,reference",
                         [(2026, FEED_2026), (2027, FEED_2027)])
def test_matches_feed_composition(year, reference):
    events = generate(year)

    extras = check_feed(events, reference)
    for event in extras:
        assert event.params["magnitude"] >= BORDERLINE_MAGNITUDE, (
            f"{event.uid} at magnitude {event.params['magnitude']} is not "
            f"borderline, yet the feed does not publish it")
    assert_unique_uids(events)
    assert events == sorted(events, key=lambda e: e.dt_utc)


def test_params_and_brightness():
    """Known magnitudes, and every param the texts read"""

    events = {e.bodies[0]: e for e in generate(2026)}

    for slug, expected in [("vesta", 6.5), ("pallas", 8.2),
                           ("nausikaa", 8.4)]:
        magnitude = events[slug].params["magnitude"]
        assert abs(magnitude - expected) <= 0.5, (
            f"{slug} at magnitude {magnitude}, expected ~{expected}")

    vesta = events["vesta"].params
    assert vesta["number"] == 4 and vesta["name"] == "Vesta"
    assert 1.1 < vesta["distance_au"] < 1.8
    assert vesta["elongation_deg"] > asteroids.MIN_ELONGATION_DEG


def test_only_bright_oppositions_published():
    """The published tenth, not some unrounded value, is under the cut.

    Rounding after the comparison would store "10.0" for an object that
    squeaked through at 9.96, and a client re-filtering on the number
    we gave it (README: "brighter than magnitude 10") would drop an
    event we had just advertised.
    """

    for event in generate(2026):
        assert event.params["magnitude"] < asteroids.MAX_MAGNITUDE


def test_catalog_parses():
    catalog = asteroids.catalog()

    assert len(catalog) > 200
    assert {p.slug for p in catalog} == {p.name.lower() for p in catalog}, (
        "a slug differs from its lowercased name -- fine in itself, but "
        "check the uid it produces")
    assert len({p.slug for p in catalog}) == len(catalog), "slug collision"
    assert all(p.magnitude_h <= mpc.MAX_H for p in catalog)
    ceres = next(p for p in catalog if p.number == 1)
    assert ceres.name == "Ceres"
    assert 2.7 < ceres.semimajor_axis_au < 2.8


def test_catalog_is_fresh():
    """Elements age: two-body propagation drifts away from their epoch.

    Refresh the catalog rather than widening this bound -- the command
    is in README.md ("Development").
    """

    epoch = asteroids.catalog()[0].epoch
    age = date.today() - epoch
    assert age < timedelta(days=MAX_CATALOG_AGE_DAYS), (
        f"skyevents/generators/asteroids.dat holds elements for epoch "
        f"{epoch}, {age.days} days old; regenerate it (see README.md)")


def test_bad_rows_are_skipped_not_raised():
    """One unparsable row costs its object, not the whole year.

    Generators run back to back in a single background pass, so raising
    here would take moon phases and eclipses down with the asteroids.
    """

    good = CATALOG_ROWS[:3]

    assert len(mpc.parse(good + ["garbage"] + CATALOG_ROWS[3:5])) == 5
    # truncated mid-line by a range request: the name would be chopped
    # and the uid would silently change, so the row must not parse
    assert len(mpc.parse(good + [good[0][:192]])) == 3
    assert len(mpc.parse(good + [good[0][:8] + "     " + good[0][13:]])) == 3


def test_empty_catalog_is_an_error(tmp_path, monkeypatch):
    """...but a catalog that yields nothing must be loud.

    An empty file from a botched refresh would otherwise read as "no
    asteroid is bright this year", for every year.
    """

    empty = tmp_path / "asteroids.dat"
    empty.write_text("# a header and nothing else\n")
    monkeypatch.setattr(asteroids, "CATALOG", empty)

    with pytest.raises(ValueError):
        asteroids.catalog.__wrapped__()  # uncached: leave the real one loaded


def test_refresh_refuses_a_short_download(tmp_path, monkeypatch):
    """A cut-short download leaves the committed catalog untouched"""

    target = tmp_path / "asteroids.dat"
    target.write_text("previous catalog")
    monkeypatch.setattr("sys.stdin", io.StringIO("".join(CATALOG_ROWS[:5])))

    with pytest.raises(SystemExit):
        mpc._main([str(target)])

    assert target.read_text() == "previous catalog"


def test_refresh_skips_rows_it_cannot_use():
    """Blank magnitudes and truncated lines drop out of the selection"""

    row = CATALOG_ROWS[0]

    assert mpc.select([row]) == [row]
    assert mpc.select([row[:8] + "     " + row[13:]]) == []
    assert mpc.select([row[:192]]) == []
    assert mpc.select([]) == []


def test_unpack_epoch():
    """Packed epochs: century letter, then base-31 month and day"""

    assert mpc.unpack_epoch("K2669") == date(2026, 6, 9)
    assert mpc.unpack_epoch("K25AV") == date(2025, 10, 31)
    assert mpc.unpack_epoch("J9611") == date(1996, 1, 1)


def test_slugify():
    assert mpc.slugify("Vesta") == "vesta"
    assert mpc.slugify("Nausikaa") == "nausikaa"
    assert mpc.slugify("van Houten") == "van_houten"
    assert mpc.slugify("Šteins") == "steins"
