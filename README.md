# skyevents

Celestial events computation service: calculates upcoming astronomical
events (moon phases, seasons, close approaches, eclipses, meteor showers…)
locally with [Skyfield](https://rhodesmill.org/skyfield/) and JPL DE440s
ephemerides — no external data services — and serves them over an HTTP API.

Built as the data source for [astro_bot](../astro_bot); see
`PLAN_EVENTS_SERVICE.md` for the roadmap.

## API

All responses are JSON unless noted. Times are UTC ISO-8601. Interactive
docs are served by FastAPI at `/docs`.

Every endpoint **rejects unknown query parameters** with a 422 — a
misspelled `?type=` (the filter is `types`, plural) fails loudly instead
of silently returning everything.

A **repeated** parameter is a 422 too. `?types=a&types=b` would otherwise
collapse to `b`, which reads as a working filter that quietly dropped
half the request — note that `params={"types": [...]}` in requests/httpx
serializes to exactly that, so pass a comma-separated string instead.

### `GET /v1/events`

The main endpoint. Returns events in a half-open window `from <= dt_utc < to`.

| Param | Required | Default | Notes |
|---|---|---|---|
| `from` | yes | — | `YYYY-MM-DD`, treated as UTC midnight |
| `to` | yes | — | `YYYY-MM-DD`, exclusive |
| `types` | no | all | comma-separated event types (see below); surrounding spaces and a trailing comma are fine, but naming none is a 422 |
| `lang` | no | `en` | `en` or `ru` |

```console
$ curl 'localhost:8000/v1/events?from=2026-08-01&to=2026-09-01&types=solar_eclipse'
{
  "events": [
    {
      "uid": "solar_eclipse:sun-moon:20260812",
      "type": "solar_eclipse",
      "dt_utc": "2026-08-12T17:45:59.809118+00:00",
      "bodies": ["sun", "moon"],
      "params": {"kind": "total", "separation_deg": 0.8919,
                 "radius_ratio": 1.0489},
      "summary": "Total solar eclipse",
      "description": "",
      "url": ""
    }
  ],
  "coverage": {"from": "2026-08-01T00:00:00+00:00",
               "to": "2026-09-01T00:00:00+00:00"}
}
```

**`coverage` is the part of the contract worth reading twice.** The cache
holds only generated years, so an empty `events` list is ambiguous on its
own. `coverage` is the intersection of the requested window with the
generated years, and events are returned only from that intersection:

- `coverage: null` — the window lies entirely outside generated years.
  This means *"not computed"*, *not* "no events". Clients must not cache
  this as an answer.
- `coverage` narrower than the request — the window was clipped; the
  uncovered remainder is unknown, not empty.

Errors: 422 for `from > to`, a window wider than 400 days, an unknown
value in `types`, an unknown `lang`, or any undeclared or repeated
parameter.

### `GET /v1/calendar.ics`

iCalendar feed for one year, format-compatible with the in-the-sky.org
feed it replaces, so the bot can switch over by swapping a URL.

| Param | Required | Default | Notes |
|---|---|---|---|
| `year` | no | current UTC year | 1900–2100 |
| `lang` | no | `en` | `en` or `ru` |

`year` is optional so the feed URL can stay a constant in client config
and keep working across a year rollover. Returns `text/calendar` with
CRLF line endings, folded to 75 octets per RFC 5545. `VEVENT` `UID`s are
identical to the `uid` field from `/v1/events`.

Returns **503 with `Retry-After`** if the requested year has not been
generated yet — deliberately an error rather than an empty calendar,
which would read as "no events this year".

### `GET /health`

```json
{"status": "ok", "generator_version": 2, "years": [2026]}
```

Answers as soon as the process is up; `years` lists what is cached so
far, so an empty list means background generation is still running, not
a failure. Returns 503 only if the cache file itself is unusable. Note
that `years` holds the next year only from December onward — a single
year mid-year is normal.

### Events

Every event carries a `uid` of the form `{type}:{bodies}:{YYYYMMDD}`.
It is deterministic and stable across regenerations (date-only, no
generator version), so clients can upsert on it.

`summary` and `description` are rendered plain text in the requested
language; `params` carries the numbers, and is what you should read
programmatically. `url` is currently always empty.

| `type` | `bodies` | `params` |
|---|---|---|
| `moon_phase` | `moon` | `phase`: `new`, `first_quarter`, `full`, `last_quarter` |
| `season` | `sun` | `season`: `march_equinox`, `june_solstice`, `september_equinox`, `december_solstice` |
| `lunar_apsis` | `moon` | `kind`: `perigee`/`apogee`; `distance_km` |
| `planet_sun` | planet | `kind`: `opposition`, `conjunction`, `inferior`, `superior` |
| `elongation` | `mercury`/`venus` | `side`: `east`/`west`; `elongation_deg` |
| `close_approach` | the two bodies | `separation_deg`, `sun_elongation_deg` |
| `lunar_eclipse` | `moon` | `kind`: `penumbral`/`partial`/`total`; `umbral_magnitude`, `penumbral_magnitude` |
| `solar_eclipse` | `sun`, `moon` | `kind`: `total`/`annular`/`partial`; `separation_deg`, `radius_ratio` |
| `meteor_shower` | shower slug | `name`, `zhr`, `solar_lon_deg` |
| `station` | planet | `direction`: `retrograde`/`direct` |

Events are computed **geocentrically** — no observer location. For
`solar_eclipse` the `kind` is the geocentric one and is approximate:
hybrids sit on the total/annular boundary, and local circumstances vary
by observer. A `station` instant is soft for the same kind of reason:
the longitude rate is passing through zero there, so the choice of
equinox and of apparent vs astrometric position moves it by tens of
minutes — expect other sources to differ by up to an hour or so.

## Development

```bash
uv sync                      # deps (creates .venv)
uv run pytest                # tests (offline)
uv run ruff check skyevents tests
```

The DE440s ephemeris (~32 MB) is downloaded on first use into `data/`
(override with the `SKYEVENTS_DATA` env variable).
