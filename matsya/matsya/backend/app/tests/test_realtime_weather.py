from datetime import datetime, timezone, timedelta


def _win():
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return now - timedelta(hours=12), now + timedelta(hours=12)


def test_dummy_weather_bounds_and_shape():
    from app.services.realtime.weather import DummyWeather
    w0, w1 = _win()
    d = DummyWeather().fetch(w0, w1, [80.15, 13.08, 80.20, 13.13])
    assert d["source"] == "dummy"
    assert all(0.0 <= c["rateMmHr"] <= 1.0 for c in d["rain"])
    assert all(40.0 <= l["fillPct"] <= 80.0 for l in d["lakes"])
    assert d["rain"], "at least the zero base cell"


def test_dummy_weather_deterministic():
    from app.services.realtime.weather import DummyWeather
    w0, w1 = _win()
    a = DummyWeather().fetch(w0, w1, [80.15, 13.08, 80.20, 13.13])
    b = DummyWeather().fetch(w0, w1, [80.15, 13.08, 80.20, 13.13])
    assert a == b


def test_source_registry():
    from app.services.realtime import weather
    assert isinstance(weather.get_source("dummy"), weather.WeatherSource)
