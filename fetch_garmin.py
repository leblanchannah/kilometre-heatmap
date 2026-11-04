#!/usr/bin/env python3
"""Fetch running activities from the Garmin Connect Personal API and write daily totals.

Writes only `date,km` rows. Raw activity JSON (which can contain GPS start
points) is never written to disk unless you pass --dump-raw, and then only
into ./raw/, which is gitignored.

Auth: GARMIN_API_KEY from the environment or .env. Create it at
Garmin Connect Web > Personal API Key. The key is exchanged for an access
token (valid 24 h) on every run, so nothing else is cached on disk.
Set GARMIN_API_BASE=https://personal.connectapi.garmin.cn for Garmin China.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo



def load_env(path: Path) -> None:
    """Minimal .env reader (KEY=value lines). Real env vars take precedence."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.removeprefix("export ").split("=", 1)
        val = val.split(" #", 1)[0].strip().strip("'\"")
        os.environ.setdefault(key.strip(), val)


load_env(Path(__file__).resolve().parent / ".env")

from make_svg import load_config


def is_run(activity: dict) -> bool:
    key = (activity.get("activityType") or {}).get("typeKey", "")
    return "running" in key  # running, trail_running, treadmill_running, track_running, ...


def local_date(activity: dict, tz: ZoneInfo) -> dt.date:
    gmt = activity.get("startTimeGMT")
    if gmt:
        t = dt.datetime.fromisoformat(gmt.replace(" ", "T")).replace(tzinfo=dt.timezone.utc)
        return t.astimezone(tz).date()
    return dt.date.fromisoformat(activity["startTimeLocal"][:10])


def daily_totals(activities: list[dict], tz: ZoneInfo) -> dict[dt.date, float]:
    totals: dict[dt.date, float] = defaultdict(float)
    for act in activities:
        if is_run(act) and act.get("distance"):
            totals[local_date(act, tz)] += act["distance"] / 1000.0
    return totals


API_BASE = os.getenv("GARMIN_API_BASE", "https://personal.connectapi.garmin.com")
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
ACTIVITIES_PATH = "/activitylist-service/activities/search/activities"
PAGE = 100


def _request(method: str, path: str, auth: str, params: dict | None = None, accept: str = "*/*"):
    url = API_BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, method=method, headers={"Authorization": auth, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300].strip()
        sys.exit(f"Garmin API {method} {path} failed: HTTP {e.code} {e.reason}" + (f"\n{detail}" if detail else ""))
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body.strip()


def get_access_token() -> str:
    key = os.getenv("GARMIN_API_KEY")
    if not key:
        sys.exit("Set GARMIN_API_KEY (env or .env). Create one at Garmin Connect Web > Personal API Key.")
    resp = _request("POST", TOKEN_PATH, f"ApiKey {key}")
    if isinstance(resp, dict):
        for field in ("access_token", "accessToken", "token"):
            if resp.get(field):
                return resp[field]
        sys.exit(f"Unexpected token response fields: {sorted(resp)}")
    return resp


def fetch_runs(token: str, start: dt.date, end: dt.date) -> list[dict]:
    activities: list[dict] = []
    offset = 0
    while True:
        page = _request("GET", ACTIVITIES_PATH, f"Bearer {token}", {
            "activityType": "running",  # parent type: includes trail, treadmill, track
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "start": offset,
            "limit": PAGE,
            "sortOrder": "asc",
        }, accept="application/json")
        activities.extend(page)
        if len(page) < PAGE:
            return activities
        offset += PAGE


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", type=Path, default=Path("config.toml"))
    p.add_argument("--days", type=int, default=380)
    p.add_argument("--out", type=Path)
    p.add_argument("--dump-raw", action="store_true", help="save raw JSON to ./raw/ (gitignored)")
    args = p.parse_args()

    cfg = load_config(args.config)
    tz = ZoneInfo(cfg["display"]["timezone"])
    out = args.out or Path(cfg["data"]["csv"])

    end = dt.datetime.now(tz).date()
    start = end - dt.timedelta(days=args.days)
    activities = fetch_runs(get_access_token(), start, end)

    if args.dump_raw:
        Path("raw").mkdir(exist_ok=True)
        Path("raw/activities.json").write_text(json.dumps(activities, indent=1))

    totals = daily_totals(activities, tz)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "km"])
        for day in sorted(totals):
            w.writerow([day.isoformat(), f"{totals[day]:.2f}"])
    print(f"wrote {out}: {len(totals)} run days, {sum(totals.values()):.1f} km")


if __name__ == "__main__":
    main()
