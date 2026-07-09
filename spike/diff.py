"""Diff our generated events against the in-the-sky.org feed.

Usage: uv run python -m spike.diff [2026 2027]

Writes a categorized report (matched with time-offset stats /
ours-only / feed-only) to data/feed/report.txt and prints it.
"""

import os
import sys
from datetime import datetime, timezone
from itertools import combinations
from statistics import median

from skyevents.ephemeris import data_dir
from spike.feedparse import parse_years
from spike.generate import Spike
from spike.records import Rec, canonical

# match windows, days: pairs farther apart than this are not the
# same event
WINDOWS = {
    "moon_phase": 0.25,
    "season": 0.25,
    "lunar_apsis": 1.0,
    "planet_sun": 1.0,
    "elongation": 1.5,
    "close_approach": 2.0,
    "lunar_eclipse": 1.0,
    "solar_eclipse": 1.0,
    "meteor_shower": 3.0,
}

TYPES = list(WINDOWS)


def expand_multi_body(feed):
    """Split the feed's 3-body close approaches into pairs"""

    out = []
    for rec in feed:
        if rec.type in ("close_approach", "ra_conjunction") \
                and len(rec.bodies) > 2:
            for pair in combinations(rec.bodies, 2):
                out.append(Rec(rec.type, canonical(pair), rec.dt,
                               rec.kind, rec.summary + " [triple]"))
        else:
            out.append(rec)
    return out


def match(ours, feed, window_days):
    """Greedy nearest-time matching within same key and window"""

    candidates = []
    for i, o in enumerate(ours):
        for j, f in enumerate(feed):
            if o.key != f.key and not (
                    o.type == "close_approach" and o.bodies == f.bodies):
                continue
            delta = abs((o.dt - f.dt).total_seconds()) / 86400
            if delta <= window_days:
                candidates.append((delta, i, j))

    candidates.sort()
    used_o, used_f, pairs = set(), set(), []
    for delta, i, j in candidates:
        if i in used_o or j in used_f:
            continue
        used_o.add(i)
        used_f.add(j)
        pairs.append((ours[i], feed[j]))

    ours_only = [o for i, o in enumerate(ours) if i not in used_o]
    feed_only = [f for j, f in enumerate(feed) if j not in used_f]
    return pairs, ours_only, feed_only


def fmt_extra(rec):
    if not rec.extra:
        return ""
    parts = [f"{k}={v:.2f}" for k, v in rec.extra.items()]
    return "  [" + ", ".join(parts) + "]"


def offsets_minutes(pairs):
    return [(f.dt - o.dt).total_seconds() / 60 for o, f in pairs]


def report_type(out, type, ours, feed):
    ours = [r for r in ours if r.type == type]
    feed_t = [r for r in feed if r.type == type]
    pairs, ours_only, feed_only = match(ours, feed_t, WINDOWS[type])

    out.append(f"\n== {type} ==")
    out.append(f"ours {len(ours)}, feed {len(feed_t)}, "
               f"matched {len(pairs)}")
    if pairs:
        deltas = [abs(d) for d in offsets_minutes(pairs)]
        out.append(f"|dt| minutes: median {median(deltas):.1f}, "
                   f"max {max(deltas):.1f}")
        kind_diff = [(o, f) for o, f in pairs if o.kind != f.kind]
        for o, f in kind_diff:
            out.append(f"  kind mismatch: ours {o} vs feed '{f.summary}'")
    for o in ours_only:
        out.append(f"  ours-only: {o}{fmt_extra(o)}")
    for f in feed_only:
        out.append(f"  feed-only: {f}  '{f.summary}'")

    # definitional comparison: our separation minima vs the feed's
    # RA-equality conjunctions for the same pair of bodies
    if type == "close_approach":
        ra = [r for r in feed if r.type == "ra_conjunction"]
        ra_pairs, _, ra_only = match(ours, ra, WINDOWS[type])
        out.append(f"\n-- vs feed RA-conjunctions: feed {len(ra)}, "
                   f"matched to our minima {len(ra_pairs)}")
        if ra_pairs:
            offs = offsets_minutes(ra_pairs)
            out.append(
                f"signed offset (RA conj - our minimum) minutes: "
                f"median {median(offs):.0f}, "
                f"min {min(offs):.0f}, max {max(offs):.0f}")
        for f in ra_only:
            out.append(f"  RA-conj without our minimum: {f}"
                       f"  '{f.summary}'")


def main(years):
    spike = Spike()
    t0 = spike.ts.utc(years[0], 1, 1)
    t1 = spike.ts.utc(years[-1] + 1, 1, 1)
    lo = datetime(years[0], 1, 1, tzinfo=timezone.utc)
    hi = datetime(years[-1] + 1, 1, 1, tzinfo=timezone.utc)

    feed = [r for r in expand_multi_body(parse_years(years))
            if lo <= r.dt < hi]
    print(f"feed: {len(feed)} in-scope events over {years}")
    ours = spike.all_events(t0, t1)
    print(f"ours: {len(ours)} generated events")

    out = [f"diff over {years}: ours {len(ours)}, "
           f"feed (in scope) {len(feed)}"]
    for type in TYPES:
        report_type(out, type, ours, feed)

    text = "\n".join(out) + "\n"
    path = os.path.join(data_dir(), "feed", "report.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    print(f"report written to {path}")


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or [2026, 2027])
