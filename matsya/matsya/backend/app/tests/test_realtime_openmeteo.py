from datetime import datetime, timezone


SAMPLE = {"latitude": 13.08, "longitude": 80.15, "hourly": {
    "time": ["2026-09-08T18:00", "2026-09-08T19:00", "2026-09-08T20:00", "2026-09-08T21:00"],
    "precipitation": [0.0, 2.5, None, 0.4]}}


def _stub_factory(payloads):
    def _fetch(url, timeout=15):
        return payloads
    return _fetch


def test_openmeteo_maps_cells_to_zones():
    from app.services.realtime.weather import OpenMeteoWeather
    w0 = datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc)
    w1 = datetime(2026, 9, 8, 22, 0, tzinfo=timezone.utc)
    src = OpenMeteoWeather(grid=1, _fetch=_stub_factory([SAMPLE]))
    d = src.fetch(w0, w1, [80.15, 13.08, 80.20, 13.13])
    assert d["source"] == "openmeteo"
    assert len(d["rain"]) >= 1
    z = d["rain"][0]
    assert z["mode"] == "variable" and z["unit"] == "rate"
    assert [p["amount"] for p in z["points"]] == [0.0, 2.5, 0.0, 0.4]
    assert d["lakes"] == []


def test_openmeteo_negative_and_null_safe():
    from app.services.realtime.weather import OpenMeteoWeather
    bad = {"latitude": 13.08, "longitude": 80.15, "hourly": {
        "time": ["2026-09-08T18:00"], "precipitation": [-3.0]}}
    src = OpenMeteoWeather(grid=1, _fetch=_stub_factory([bad]))
    d = src.fetch(datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc),
                  datetime(2026, 9, 8, 19, 0, tzinfo=timezone.utc),
                  [80.15, 13.08, 80.20, 13.13])
    assert d["rain"][0]["points"][0]["amount"] == 0.0


def test_openmeteo_registered():
    from app.services.realtime import weather
    src = weather.get_source("openmeteo")
    assert type(src).__name__ == "OpenMeteoWeather"
    assert isinstance(src, weather.WeatherSource)


def test_openmeteo_cells_parse_as_zones():
    from datetime import datetime, timezone
    from app.services.realtime.weather import OpenMeteoWeather
    from app.services.rainfall_zones import parse_zones
    w0 = datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc)
    w1 = datetime(2026, 9, 8, 22, 0, tzinfo=timezone.utc)
    src = OpenMeteoWeather(grid=3, _fetch=_stub_factory([SAMPLE] * 9))
    d = src.fetch(w0, w1, [80.15, 13.08, 80.20, 13.13])
    zl, dropped = parse_zones({"zones": d["rain"]})
    assert len(zl) == 9 and dropped == []


def test_openmeteo_requests_utc_timezone():
    from datetime import datetime, timezone
    from app.services.realtime.weather import OpenMeteoWeather
    seen = {}

    def _cap(url, timeout=15):
        seen["url"] = url
        return {"hourly": {"time": [], "precipitation": []}}

    src = OpenMeteoWeather(grid=1, _fetch=_cap)
    src.fetch(datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc),
              datetime(2026, 9, 8, 22, 0, tzinfo=timezone.utc),
              [80.15, 13.08, 80.20, 13.13])
    assert "timezone=UTC" in seen["url"]
    assert "forecast_days=2" in seen["url"]


def test_openmeteo_cell_series_contract_for_grid_ui():
    """The live grid UI depends on this shape: one variable hourly series
    per cell, totalTime == the 24h tick window, maxRain == peak."""
    from datetime import timedelta
    from app.services.realtime.weather import OpenMeteoWeather
    from app.services.realtime.manager import WINDOW_HOURS
    now = datetime(2026, 9, 15, 8, 44, tzinfo=timezone.utc)
    w0, w1 = now - timedelta(hours=WINDOW_HOURS), now + timedelta(hours=WINDOW_HOURS)
    base = datetime(2026, 9, 14, 0, 0)
    times = [(base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(72)]
    vals = [float(i % 5) for i in range(72)]
    payload = {"hourly": {"time": times, "precipitation": vals}}
    src = OpenMeteoWeather(grid=12, _fetch=_stub_factory([payload] * 144))
    d = src.fetch(w0, w1, [80.13968, 13.01593, 80.28967, 13.14146])
    assert len(d["rain"]) == 144
    for z in d["rain"]:
        assert z["mode"] == "variable" and z["unit"] == "rate"
        assert z["totalTime"] == 2 * WINDOW_HOURS == 24
        pts = z["points"]
        assert len(pts) == 24
        ts = [p["time"] for p in pts]
        assert ts == sorted(ts) and ts[0] >= 0 and ts[-1] < 24
        assert z["maxRain"] == max(p["amount"] for p in pts)
        poly = z["polygon"]
        assert poly["type"] == "Polygon" and len(poly["coordinates"][0]) >= 4
