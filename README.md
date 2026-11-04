# kilometre-heatmap

A GitHub-contributions-style heatmap of daily running distance, in orange.
It's built from Garmin Connect data by a job that runs on your own machine.

[![Run heatmap](runs.svg)](https://github.com/leblanchannah/kilometre-heatmap)

*(The SVG committed now is rendered from `sample_daily_km.csv`. The first real update replaces it.)*

The SVG follows the viewer's theme: dark by default, light when the system is in light mode. Hovering a square shows that day's distance.

## How it works

| File | Role |
|---|---|
| `fetch_garmin.py` | Logs in with [`garminconnect`](https://github.com/cyberjunky/python-garminconnect), keeps running activities only (road, trail, treadmill, track), converts start times to your timezone, and writes `daily_km.csv` (`date,km`). |
| `make_svg.py` | Turns `daily_km.csv` into `runs.svg` (a 7×53 grid with 4 orange levels). It uses only the standard library. |
| `update.sh` | Fetches, renders, then commits and pushes `runs.svg` and `daily_km.csv` if they changed. |
| `config.example.toml` | Username, units (km/mi), timezone, level thresholds, colours. |
| `sample_daily_km.csv` | Fake data, so you can try the renderer without a Garmin account. |

**Privacy:** only daily totals and the SVG are committed. Raw activity JSON can contain GPS start points, so it is never written unless you pass `--dump-raw`, and then only to `raw/`, which is gitignored. Credentials stay in `.env`, and tokens stay in `~/.garminconnect`. Neither goes into the repo.

## Try it with sample data

Needs Python 3.11 or newer.

```bash
python3 make_svg.py --csv sample_daily_km.csv --out runs.svg
```

## Set up with Garmin

```bash
git clone https://github.com/leblanchannah/kilometre-heatmap && cd kilometre-heatmap
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp config.example.toml config.toml   # edit timezone, colours, thresholds
cp .env.example .env                 # add your Garmin email/password
.venv/bin/python fetch_garmin.py     # first run: enter your MFA code if asked
.venv/bin/python make_svg.py
```

After the first login, the cached tokens are used and no prompt appears. If Garmin changes its login flow, run `pip install -U garminconnect`.

## Schedule it

**cron** (Linux/macOS), daily at 21:30:

```
30 21 * * * /path/to/kilometre-heatmap/update.sh >> /tmp/run-heatmap.log 2>&1
```

**launchd** (macOS): save this as `~/Library/LaunchAgents/com.runheatmap.update.plist`, then run `launchctl load` on it:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.runheatmap.update</string>
  <key>ProgramArguments</key><array><string>/path/to/kilometre-heatmap/update.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>21</integer><key>Minute</key><integer>30</integer></dict>
  <key>StandardOutPath</key><string>/tmp/run-heatmap.log</string>
  <key>StandardErrorPath</key><string>/tmp/run-heatmap.log</string>
</dict></plist>
```

The job pushes with your normal git credentials, so set up an SSH key or a credential helper first.

## Add it to your profile README

```markdown
[![Daily running km](https://raw.githubusercontent.com/leblanchannah/kilometre-heatmap/main/runs.svg)](https://github.com/leblanchannah/kilometre-heatmap)
```

GitHub's image proxy can cache the image for a while. If updates lag too much, have `update.sh` also copy `runs.svg` into your `username/username` repo and push it there.

## Tests

The tests use mock Garmin responses only:

```bash
python3 -m pytest tests
```
