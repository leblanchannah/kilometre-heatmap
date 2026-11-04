#!/usr/bin/env bash
# Fetch from Garmin, render runs.svg, commit and push if anything changed.
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-.venv/bin/python}"; [ -x "$PY" ] || PY=python3

"$PY" fetch_garmin.py
"$PY" make_svg.py

git add runs.svg daily_km.csv
if git diff --cached --quiet; then
  echo "no changes"; exit 0
fi
git commit -m "Update run heatmap $(date +%F)"
git push
