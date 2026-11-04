#!/usr/bin/env python3
"""Render a GitHub-contributions-style heatmap of daily running distance.

Input:  CSV with columns date,km  (YYYY-MM-DD, float)
Output: a standalone SVG (dark theme by default, light theme via
        prefers-color-scheme so it matches the viewer's GitHub theme).

Usage:  python make_svg.py [--config config.toml] [--csv FILE] [--out FILE]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import tomllib
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

KM_PER_MI = 1.609344

DEFAULT_CONFIG = {
    "display": {"username": "", "units": "km", "timezone": "America/Toronto", "weeks": 53},
    "data": {"csv": "daily_km.csv", "output": "runs.svg"},
    "levels": {"thresholds": [0.01, 5, 10, 15]},
    "colors": {
        "dark": {
            "background": "#22272e", "border": "#444c56", "text": "#adbac7",
            "empty": "#2d333b",
            "levels": ["#5c2b0b", "#9a4413", "#d9661a", "#ffa657"],
        },
        "light": {
            "background": "#ffffff", "border": "#d0d7de", "text": "#57606a",
            "empty": "#ebedf0",
            "levels": ["#ffd8b5", "#ffa657", "#e8710a", "#9a4413"],
        },
    },
}

# Geometry (px)
CELL = 10
GAP = 3
STEP = CELL + GAP
PAD_X = 20
TITLE_H = 34
LEFT = PAD_X + 30          # room for Mon/Wed/Fri
TOP = TITLE_H + 34         # room for month labels inside the box
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"


def merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load_config(path: Path | None) -> dict:
    if path and path.exists():
        with path.open("rb") as f:
            return merge(DEFAULT_CONFIG, tomllib.load(f))
    return DEFAULT_CONFIG


def read_daily(path: Path) -> dict[dt.date, float]:
    totals: dict[dt.date, float] = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            d = dt.date.fromisoformat(row["date"].strip())
            totals[d] = totals.get(d, 0.0) + float(row["km"] or 0)
    return totals


def level_for(value: float, thresholds: list[float]) -> int:
    if value <= 0:
        return 0
    lvl = 1
    for i, t in enumerate(thresholds):
        if value >= t:
            lvl = i + 1
    return lvl


def fmt_num(x: float) -> str:
    return f"{x:,.0f}" if x >= 100 else f"{x:,.1f}".rstrip("0").rstrip(".")


def render(daily_km: dict[dt.date, float], cfg: dict, today: dt.date | None = None) -> str:
    disp = cfg["display"]
    units = disp["units"]
    factor = 1 / KM_PER_MI if units == "mi" else 1.0
    weeks = int(disp["weeks"])
    thresholds = cfg["levels"]["thresholds"]
    dark, light = cfg["colors"]["dark"], cfg["colors"]["light"]

    if today is None:
        today = dt.datetime.now(ZoneInfo(disp["timezone"])).date()
    # Columns are Sunday-start weeks; the last column holds today.
    last_sunday = today - dt.timedelta(days=(today.weekday() + 1) % 7)
    start = last_sunday - dt.timedelta(weeks=weeks - 1)
    year_ago = today - dt.timedelta(days=365)

    total = sum(v for d, v in daily_km.items() if year_ago < d <= today) * factor
    run_days = sum(1 for d, v in daily_km.items() if year_ago < d <= today and v > 0)

    grid_w = weeks * STEP - GAP
    box_x, box_y = PAD_X, TITLE_H + 8
    box_w = (LEFT - PAD_X) + grid_w + 2 * PAD_X - 6
    width = box_x + box_w + PAD_X
    grid_h = 7 * STEP - GAP
    legend_y = TOP + grid_h + 14
    box_h = legend_y + CELL + 16 - box_y
    height = box_y + box_h + 2

    out: list[str] = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
      f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="t">')
    title = f"{fmt_num(total)} {units} run in the last year"
    who = f"{disp['username']}: " if disp.get("username") else ""
    a(f'<title id="t">{escape(who + title)} ({run_days} days)</title>')

    css_levels_dark = "".join(f".l{i+1}{{fill:{c}}}" for i, c in enumerate(dark["levels"]))
    css_levels_light = "".join(f".l{i+1}{{fill:{c}}}" for i, c in enumerate(light["levels"]))
    a("<style>"
      f"svg{{font-family:{FONT}}}"
      f".bg{{fill:{dark['background']}}}.box{{fill:none;stroke:{dark['border']}}}"
      f".tx{{fill:{dark['text']};font-size:10px}}.hd{{fill:{dark['text']};font-size:16px}}"
      f".l0{{fill:{dark['empty']}}}{css_levels_dark}"
      "rect.c{shape-rendering:geometricPrecision}"
      "@media (prefers-color-scheme: light){"
      f".bg{{fill:{light['background']}}}.box{{stroke:{light['border']}}}"
      f".tx,.hd{{fill:{light['text']}}}.l0{{fill:{light['empty']}}}{css_levels_light}"
      "}</style>")
    a(f'<rect class="bg" width="{width}" height="{height}" rx="6"/>')
    a(f'<text class="hd" x="{PAD_X}" y="{TITLE_H - 8}">{escape(title)}</text>')
    a(f'<rect class="box" x="{box_x + .5}" y="{box_y + .5}" width="{box_w}" height="{box_h}" rx="6"/>')

    # Month labels: at the first column whose first in-range day starts a month
    last_label_x = -999
    for w in range(weeks):
        col_start = start + dt.timedelta(weeks=w)
        for d in range(7):
            day = col_start + dt.timedelta(days=d)
            if day.day == 1 or (w == 0 and d == 0):
                x = LEFT + w * STEP
                # skip a partial first month if the next label would collide
                if x - last_label_x >= 3 * STEP and not (w == 0 and day.day > 21):
                    a(f'<text class="tx" x="{x}" y="{TOP - 7}">{day.strftime("%b")}</text>')
                    last_label_x = x
                break

    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        a(f'<text class="tx" x="{PAD_X + 6}" y="{TOP + row * STEP + CELL - 1}">{name}</text>')

    for w in range(weeks):
        for d in range(7):
            day = start + dt.timedelta(weeks=w, days=d)
            if day > today:
                continue
            km = daily_km.get(day, 0.0)
            v = km * factor
            lvl = level_for(v, thresholds)
            label = f"{fmt_num(v)} {units} on {day:%b %-d, %Y}" if v > 0 else f"No runs on {day:%b %-d, %Y}"
            a(f'<rect class="c l{lvl}" x="{LEFT + w * STEP}" y="{TOP + d * STEP}" '
              f'width="{CELL}" height="{CELL}" rx="2"><title>{label}</title></rect>')

    # Legend (right-aligned under the grid)
    lx_end = LEFT + grid_w
    more_w = 26
    x = lx_end - more_w
    a(f'<text class="tx" x="{x + 4}" y="{legend_y + CELL - 1}">More</text>')
    for lvl in range(4, -1, -1):
        x -= STEP
        a(f'<rect class="l{lvl}" x="{x}" y="{legend_y}" width="{CELL}" height="{CELL}" rx="2"/>')
    a(f'<text class="tx" x="{x - 4}" y="{legend_y + CELL - 1}" text-anchor="end">Less</text>')
    a(f'<text class="tx" x="{LEFT}" y="{legend_y + CELL - 1}">{run_days} run days · '
      f'levels at {", ".join(fmt_num(t) for t in thresholds[1:])} {units}</text>')
    a("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", type=Path, default=Path("config.toml"))
    p.add_argument("--csv", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--today", type=dt.date.fromisoformat, help="override end date (YYYY-MM-DD)")
    args = p.parse_args()

    cfg = load_config(args.config)
    csv_path = args.csv or Path(cfg["data"]["csv"])
    out_path = args.out or Path(cfg["data"]["output"])
    svg = render(read_daily(csv_path), cfg, today=args.today)
    out_path.write_text(svg, encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
