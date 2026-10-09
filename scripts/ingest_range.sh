#!/usr/bin/env bash
set -u

usage() { echo "usage: $0 YYYY-MM-DD YYYY-MM-DD [log_file]" >&2; exit 2; }
[ $# -ge 2 ] || usage

start="$1"
end="$2"
log="${3:-/dev/stdout}"
py="${PYTHON:-.venv/Scripts/python}"

day="$start"
while [ "$(date -d "$day" +%s)" -le "$(date -d "$end" +%s)" ]; do
  fecha="$(date -d "$day" +%d%m%Y)"
  if [ -f "data/oc_items_${fecha}.parquet" ]; then
    echo "skip $fecha (already ingested)" >> "$log"
  elif "$py" -m osint_mercado.ingest --fecha "$fecha" --codes data/rm_municipal_codes.json \
      --out data --max-per-organism 200 --pace 0.25 >> "$log" 2>&1; then
    echo "done $fecha" >> "$log"
  else
    echo "FAILED $fecha" >> "$log"
  fi
  day="$(date -d "$day + 1 day" +%Y-%m-%d)"
done
echo "finished $start..$end" >> "$log"
