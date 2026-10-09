#!/usr/bin/env bash
set -u

usage() { echo "usage: $0 START END [log_file]  (dates YYYY-MM-DD; START after END runs newest-first)" >&2; exit 2; }
[ $# -ge 2 ] || usage

start="$1"
end="$2"
log="${3:-/dev/stdout}"
py="${PYTHON:-.venv/Scripts/python}"

step="+ 1 day"
cmp="-le"
if [ "$(date -d "$start" +%s)" -gt "$(date -d "$end" +%s)" ]; then
  step="- 1 day"
  cmp="-ge"
fi

day="$start"
while [ "$(date -d "$day" +%s)" "$cmp" "$(date -d "$end" +%s)" ]; do
  fecha="$(date -d "$day" +%d%m%Y)"
  if [ -f "data/oc_items_${fecha}.parquet" ] && [ ! -f "data/oc_items_${fecha}.gaps.json" ]; then
    echo "skip $fecha (already ingested)" >> "$log"
  else
    "$py" -m osint_mercado.ingest --fecha "$fecha" --codes data/rm_municipal_codes.json \
      --out data --max-per-organism 200 --pace "${PACE:-1.0}" >> "$log" 2>&1
    status=$?
    if [ "$status" -eq 3 ]; then
      echo "STOPPED at $fecha (quota or circuit breaker, see above)" >> "$log"
      exit 3
    elif [ "$status" -ne 0 ]; then
      echo "FAILED $fecha (exit $status)" >> "$log"
    elif [ -f "data/oc_items_${fecha}.gaps.json" ]; then
      echo "done $fecha with gaps (re-run to fill them from cache)" >> "$log"
    else
      echo "done $fecha" >> "$log"
    fi
  fi
  day="$(date -d "$day $step" +%Y-%m-%d)"
done
echo "finished $start..$end" >> "$log"
