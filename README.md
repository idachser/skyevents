# skyevents

Celestial events computation service: calculates upcoming astronomical
events (moon phases, seasons, close approaches, eclipses, meteor showers…)
locally with [Skyfield](https://rhodesmill.org/skyfield/) and JPL DE440s
ephemerides — no external data services — and serves them over an HTTP API.

Built as the data source for [astro_bot](../astro_bot); see
`PLAN_EVENTS_SERVICE.md` for the roadmap.

## Development

```bash
uv sync                      # deps (creates .venv)
uv run pytest                # tests (offline)
uv run ruff check skyevents tests
```

The DE440s ephemeris (~32 MB) is downloaded on first use into `data/`
(override with the `SKYEVENTS_DATA` env variable).
