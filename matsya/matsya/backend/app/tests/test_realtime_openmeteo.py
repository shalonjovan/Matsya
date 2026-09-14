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
