# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

## Project

HTTP API service that computes celestial events (moon phases, seasons,
apsides, oppositions/conjunctions, elongations, close approaches,
eclipses, meteor showers) with Skyfield + JPL DE440s ephemerides, offline.
It replaces the In-The-Sky.org iCal feed as the data source for the
Telegram bot in the sibling `astro_bot` repository; the bot talks to this
service over HTTP only. `PLAN_EVENTS_SERVICE.md` is the roadmap — keep its
checkboxes up to date.

## Commands

```bash
uv sync                            # deps (creates .venv)
uv run pytest                      # tests (offline — never download in tests)
uv run flake8 skyevents tests      # lint
```

## Architecture

- `skyevents/model.py` — `Event` (pydantic) with deterministic `uid`
  (`{type}:{bodies}:{YYYYMMDD}`). The uid must stay stable across
  regenerations: date-only (no time), never include a generator version.
- `skyevents/ephemeris.py` — Skyfield `Loader` rooted at `SKYEVENTS_DATA`
  (default `data/`, gitignored); DE440s downloads there on first use.
- `skyevents/generators/` — one module per event type, each exposing
  `generate(year) -> list[Event]`. Events are computed geocentrically.
- Events carry numeric params, not prose; user-facing texts (en/ru) are
  rendered from templates by event type (plan stage 3).
- API contract (plan stage 4): versioned paths (`/v1/…`), explicit cache
  coverage in responses — an empty window outside generated years must
  not look like "no events".

## Testing conventions

Tests run offline. Generator tests assert against known reference events
with tolerances fixed in the plan's stage-0 spike; never fetch feeds or
ephemerides from the network in tests (the ephemeris file in `data/` may
be present locally, but CI has none). `tests/conftest.py` points
`SKYEVENTS_DATA` at `tests/data/`, which holds a committed jplephem
excerpt of DE440s covering 2025–2030 (~0.7 MB) — keep generator test
years inside that range. Regenerate with:
`uv run python -m jplephem excerpt 2025/1/1 2030/12/31 data/de440s.bsp
tests/data/de440s.bsp`.
