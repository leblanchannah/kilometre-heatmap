#!/usr/bin/env python3
"""Fetch running activities from Garmin Connect and write daily totals.

Writes only `date,km` rows. Raw activity JSON (which can contain GPS start
points) is never written to disk unless you pass --dump-raw, and then only
into ./raw/, which is gitignored.

Credentials: GARMIN_EMAIL / GARMIN_PASSWORD from the environment or .env.
Tokens are cached in GARMINTOKENS (default ~/.garminconnect), outside the repo.
The first login with MFA must be run interactively in a terminal.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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


def login():
    from garminconnect import Garmin

    tokenstore = os.path.expanduser(os.getenv("GARMINTOKENS", "~/.garminconnect"))
    try:
        g = Garmin()
        g.login(tokenstore)
        return g
    except Exception:
        pass
    email, password = os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD")
    if not email or not password:
        sys.exit("Set GARMIN_EMAIL and GARMIN_PASSWORD (env or .env).")
    g = Garmin(email=email, password=password, prompt_mfa=lambda: input("Garmin MFA code: "))
    g.login()
    g.garth.dump(tokenstore)
    return g


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
    g = login()
    activities = g.get_activities_by_date(start.isoformat(), end.isoformat())

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
