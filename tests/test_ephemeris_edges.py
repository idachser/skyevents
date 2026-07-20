"""Every generator must survive the edge years of the ephemeris.

find_minima/find_maxima sample one step outside the window they are
given and the ephemeris raises rather than extrapolate, so a generator
that hands over a bare year window crashes on the first year an
ephemeris covers. The committed excerpt covers 2025-2030, which
CLAUDE.md documents as the usable test range.
"""

import pytest

from skyevents.generators import MODULES, generate_year
from skyevents.generators.base import context

EDGE_YEARS = (2025, 2030)


@pytest.mark.parametrize("year", EDGE_YEARS)
@pytest.mark.parametrize(
    "module", MODULES, ids=[m.__name__.rsplit(".", 1)[-1] for m in MODULES])
def test_generator_runs_at_ephemeris_edge(module, year):
    events = module.generate(year)
    assert all(e.dt_utc.year == year for e in events)


@pytest.mark.parametrize("year", EDGE_YEARS)
def test_generate_year_at_ephemeris_edge(year):
    assert generate_year(year)


@pytest.mark.parametrize("year", [2024, 2031, 2032])
def test_year_outside_coverage_is_an_explicit_error(year):
    """Not a silent empty result: an uncovered year must say so."""

    with pytest.raises(ValueError, match="outside the ephemeris coverage"):
        context().search_window(year, pad_days=2.0, step_days=0.05)
    with pytest.raises(ValueError, match="outside the ephemeris coverage"):
        generate_year(year)
