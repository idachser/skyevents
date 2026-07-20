#!/usr/bin/env bash
# Mechanical half of the smoke run: tests, lint, and the HTTP contract
# matrix. Astronomy correctness is not checked here -- see SKILL.md.
#
# Prints one PASS/FAIL line per check and exits non-zero if any failed.
# Usage: check.sh [--no-tests]

set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1

run_tests=1
[ "${1:-}" = "--no-tests" ] && run_tests=0

failed=0
pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s -- %s\n' "$1" "$2"; failed=1; }
note() { printf 'NOTE  %s\n' "$1"; }

# --- tests and lint ---------------------------------------------------

if [ "$run_tests" = 1 ]; then
  out=$(uv run pytest -q 2>&1)
  if [ $? -eq 0 ]; then pass "pytest ($(printf '%s' "$out" | tail -1))"
  else fail "pytest" "$(printf '%s' "$out" | tail -15)"; fi
fi

out=$(uv run ruff check skyevents tests 2>&1)
if [ $? -eq 0 ]; then pass "ruff"; else fail "ruff" "$out"; fi

# --- server -----------------------------------------------------------

port=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
log=$(mktemp)
uv run uvicorn skyevents.api:app --port "$port" >"$log" 2>&1 &
server=$!
cleanup() { kill "$server" 2>/dev/null; wait "$server" 2>/dev/null; rm -f "$log"; }
trap cleanup EXIT

base="http://127.0.0.1:$port"
for _ in $(seq 60); do
  curl -sf -o /dev/null "$base/health" && break
  kill -0 "$server" 2>/dev/null || { fail "server start" "$(tail -20 "$log")"; exit 1; }
  sleep 1
done

# code URL [expected-substring]
expect() {
  local label="$1" want="$2" url="$3" needle="${4:-}"
  local body code
  body=$(curl -s -w '\n%{http_code}' "$base$url")
  code=${body##*$'\n'}
  body=${body%$'\n'*}
  if [ "$code" != "$want" ]; then
    fail "$label" "want HTTP $want, got $code"
  elif [ -n "$needle" ] && ! printf '%s' "$body" | grep -q "$needle"; then
    fail "$label" "response lacks '$needle'"
  else
    pass "$label"
  fi
}

json() { curl -s "$base$1" | python3 -c "import json,sys;d=json.load(sys.stdin);$2"; }

# --- health and coverage ---------------------------------------------

expect "health 200" 200 "/health" '"status":"ok"'

years=$(json "/health" 'print(" ".join(map(str,d["years"])))' 2>/dev/null)
if [ -z "$years" ]; then
  note "cache is empty -- background generation is still running."
  note "Endpoint checks below will see no events; re-run in a few minutes."
  exit "$failed"
fi
note "cached years: $years"
year=${years%% *}
uncached=$(( ${years##* } + 5 ))

expect "events: happy window" 200 \
  "/v1/events?from=$year-01-01&to=$year-01-31" '"coverage"'
expect "events: outside coverage reports coverage:null" 200 \
  "/v1/events?from=$uncached-01-01&to=$uncached-02-01" '"coverage":null'
expect "events: from > to rejected" 422 \
  "/v1/events?from=$year-09-01&to=$year-08-01"
expect "events: window > 400d rejected" 422 \
  "/v1/events?from=$year-01-01&to=$((year+2))-01-01"
expect "events: unknown type rejected" 422 \
  "/v1/events?from=$year-01-01&to=$year-03-01&types=nonsense"

# --- filtering and i18n ----------------------------------------------

all=$(json "/v1/events?from=$year-01-01&to=$((year+1))-01-01" 'print(len(d["events"]))')
some=$(json "/v1/events?from=$year-01-01&to=$((year+1))-01-01&types=moon_phase" \
  'print(len(d["events"]), len({e["type"] for e in d["events"]}-{"moon_phase"}))')
set -- $some
if [ "$1" -gt 0 ] && [ "$1" -lt "$all" ] && [ "$2" = 0 ]; then
  pass "events: types filter narrows to moon_phase ($1 of $all)"
else
  fail "events: types filter" "got $1 of $all, $2 foreign types"
fi

en=$(json "/v1/events?from=$year-01-01&to=$year-02-01" 'print(d["events"][0]["summary"])')
ru=$(json "/v1/events?from=$year-01-01&to=$year-02-01&lang=ru" 'print(d["events"][0]["summary"])')
if [ -n "$ru" ] && [ "$ru" != "$en" ]; then
  pass "events: lang=ru renders Russian ('$en' -> '$ru')"
else
  fail "events: lang=ru" "en='$en' ru='$ru'"
fi

# --- ics --------------------------------------------------------------

expect "ics: year required" 422 "/v1/calendar.ics"

ics=$(mktemp)
code=$(curl -s -o "$ics" -w '%{http_code}' "$base/v1/calendar.ics?year=$year")
ctype=$(curl -s -o /dev/null -w '%{content_type}' "$base/v1/calendar.ics?year=$year")
n=$(grep -c '^BEGIN:VEVENT' "$ics")
if [ "$code" = 200 ] && [ "$n" -gt 0 ] && [[ "$ctype" == text/calendar* ]]; then
  pass "ics: $n VEVENTs, $ctype"
else
  fail "ics" "HTTP $code, $n VEVENTs, ctype=$ctype"
fi

grep -q '^BEGIN:VCALENDAR' "$ics" && grep -q '^END:VCALENDAR' "$ics" \
  && pass "ics: VCALENDAR wrapper" || fail "ics: VCALENDAR wrapper" "missing"

# LC_ALL=C so awk counts octets, not characters -- the limit is on bytes
# and the Russian texts are multi-byte. CR is stripped: it is the CRLF
# terminator, not content.
long=$(LC_ALL=C awk '{ sub(/\r$/,""); if (length($0) > 75) c++ } END { print c+0 }' "$ics")
[ "$long" = 0 ] && pass "ics: RFC 5545 folding (no line > 75 octets)" \
  || fail "ics: RFC 5545 folding" "$long lines exceed 75 octets"

# UIDs must be identical across endpoints -- they are the bot's dedup key.
# ICS lines end in CRLF (RFC 5545), so strip CR before comparing or every
# line looks different.
ics_uids=$(grep '^UID:' "$ics" | sed 's/^UID://; s/\r$//' | sort)
api_uids=$(json "/v1/events?from=$year-01-01&to=$((year+1))-01-01" \
  'print("\n".join(e["uid"] for e in d["events"]))' | sort)
if [ "$ics_uids" = "$api_uids" ]; then
  pass "uids match between /v1/events and /v1/calendar.ics"
else
  fail "uid consistency" \
    "$(diff <(printf '%s\n' "$ics_uids") <(printf '%s\n' "$api_uids") | head -10)"
fi
rm -f "$ics"

# --- server health after the run --------------------------------------

grep -qE 'Traceback|ERROR' "$log" \
  && fail "server log clean" "$(grep -nE 'Traceback|ERROR' "$log" | head -5)" \
  || pass "server log clean"

exit "$failed"
