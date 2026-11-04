import datetime as dt
from zoneinfo import ZoneInfo

from fetch_garmin import daily_totals
from make_svg import DEFAULT_CONFIG, level_for, render

TZ = ZoneInfo("America/Toronto")


def test_late_evening_utc_run_counts_on_local_day():
    acts = [  # mock, redacted Garmin responses
        {"activityType": {"typeKey": "running"}, "distance": 5000.0, "startTimeGMT": "2026-10-02 02:30:00"},
        {"activityType": {"typeKey": "trail_running"}, "distance": 2500.0, "startTimeGMT": "2026-10-01 12:00:00"},
        {"activityType": {"typeKey": "cycling"}, "distance": 40000.0, "startTimeGMT": "2026-10-01 12:00:00"},
    ]
    assert daily_totals(acts, TZ) == {dt.date(2026, 10, 1): 7.5}


def test_levels():
    t = [0.01, 5, 10, 15]
    assert [level_for(v, t) for v in (0, 2, 5, 9.9, 10, 30)] == [0, 1, 2, 2, 3, 4]


def test_render_grid():
    svg = render({dt.date(2026, 11, 2): 12.0}, DEFAULT_CONFIG, today=dt.date(2026, 11, 4))
    assert svg.count('class="c ') == 52 * 7 + 4  # last column runs Sun..Wed
    assert "12 km on Nov 2, 2026" in svg and "12 km run in the last year" in svg


def test_fetch_paginates_and_exchanges_key(monkeypatch):
    import fetch_garmin as fg

    calls = []
    run = {"activityType": {"typeKey": "running"}, "distance": 1000.0, "startTimeGMT": "2026-10-01 12:00:00"}

    def fake(method, path, auth, params=None):
        calls.append((method, path, auth, params and params["start"]))
        if path == fg.TOKEN_PATH:
            return {"access_token": "tok"}
        return [run] * (fg.PAGE if params["start"] == 0 else 3)

    monkeypatch.setenv("GARMIN_API_KEY", "k")
    monkeypatch.setattr(fg, "_request", fake)
    acts = fg.fetch_runs(fg.get_access_token(), dt.date(2026, 1, 1), dt.date(2026, 11, 4))
    assert len(acts) == fg.PAGE + 3
    assert calls[0][:3] == ("POST", fg.TOKEN_PATH, "ApiKey k")
    assert [c[2:] for c in calls[1:]] == [("Bearer tok", 0), ("Bearer tok", fg.PAGE)]
