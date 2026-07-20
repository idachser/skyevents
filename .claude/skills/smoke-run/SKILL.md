---
name: smoke-run
description: End-to-end check that the skyevents service works — runs tests and lint, boots the API on a scratch port, exercises the HTTP contract, and spot-checks the astronomy against known reference events. Use when asked to "check the service", "проверь работу сервиса", verify the API after a change, or before a release.
---

# Smoke run

Two halves. `check.sh` does the mechanical part; you do the judgement part.
Do not skip the second half — every contract check can pass while the
generators quietly emit wrong dates.

## 1. Mechanical checks

```bash
.claude/skills/smoke-run/check.sh
```

Runs pytest and ruff, boots uvicorn on a free port, and asserts the HTTP
contract: health, coverage semantics, `from > to`, the 400-day window cap,
unknown `types`, the `types` filter, `lang=ru`, the ICS feed (content type,
VCALENDAR wrapper, RFC 5545 folding), and that UIDs agree between
`/v1/events` and `/v1/calendar.ics`. It prints one `PASS`/`FAIL` line per
check, tears the server down on exit, and exits non-zero if anything failed.

Pass `--no-tests` to skip pytest when you have just run it yourself.

The script derives its test year from `/health`, so it does not go stale.
If the cache is empty it says so and stops — background generation takes
minutes on a cold `data/`; re-run once `/health` lists a year.

## 2. Astronomy spot-check

The contract tests prove the service answers; they do not prove it is
right. Pull a year of events and compare a handful against values you can
verify independently:

```bash
curl -s "http://127.0.0.1:$PORT/v1/events?from=2026-01-01&to=2026-12-31" \
  | python3 -c 'import json,sys;[print(e["dt_utc"], e["summary"]) for e in json.load(sys.stdin)["events"]]'
```

Check at least: **eclipses** (dates *and* kind — annular vs total vs
partial), **solstices and equinoxes** (to the minute), one **major meteor
shower** peak, and one **planetary opposition**. These are the ones with
published values that are easy to confirm from memory or a reference.

Known-good for 2026, verified 2026-07-20:

| Event | Expected |
|---|---|
| Annular solar eclipse | 2026-02-17 |
| Total lunar eclipse | 2026-03-03 |
| Total solar eclipse | 2026-08-12 |
| Partial lunar eclipse | 2026-08-28 |
| June solstice | 2026-06-21 08:24 UTC |
| Perseids peak | 2026-08-13 |
| Jupiter at opposition | 2026-01-10 |

For other years, derive fresh reference values rather than assuming this
table transfers.

## Gotchas

- The query parameter is `types` (plural, comma-separated), not `type`.
  FastAPI ignores unknown query params silently, so `type=solar_eclipse`
  returns **every** event and looks like a broken filter. Easy to
  misdiagnose as a bug.
- `/v1/calendar.ics` requires `year`; bare `/v1/calendar.ics` is a 422 by
  design.
- `/health` lists next year only from December (`needed_years()` in
  `skyevents/api.py`). Seeing a single year mid-year is correct, not a
  cache failure.
- The script uses the real `data/` cache. To check a cold start instead,
  point `SKYEVENTS_CACHE` at a scratch path first — but expect minutes of
  generation before events appear.

## Reporting

Give the user a short table of what passed, then the astronomy spot-check
result, then anything worth flagging. State failures plainly with the
output. If the script exits clean and the reference events match, say the
service works — no hedging.
