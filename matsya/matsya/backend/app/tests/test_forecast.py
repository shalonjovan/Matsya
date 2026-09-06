def _fake_fetch_ok(lat, lon, hours):
    return {"hourly": {"precipitation": [2.0 * i for i in range(48)]}}


def test_forecast_uses_peak_and_caches(tmp_path, monkeypatch):
    import app.services.rainfall_forecast as rf
    monkeypatch.setattr(rf, "_cache_path", lambda bbox, hours: tmp_path / "c.json")
    r1 = rf.forecast_rain([80.15, 13.08, 80.20, 13.13], hours=6, _fetch=_fake_fetch_ok)
    assert r1["source"] == "open-meteo" and r1["cached"] is False
    assert r1["rateMmHr"] == 10.0 and r1["durationHr"] == 6 and len(r1["hourly"]) == 6
    r2 = rf.forecast_rain([80.15, 13.08, 80.20, 13.13], hours=6,
                          _fetch=lambda *a: (_ for _ in ()).throw(AssertionError("must use cache")))
    assert r2["cached"] is True and r2["rateMmHr"] == 10.0


def test_forecast_offline_raises_named_error():
    from app.services.rainfall_forecast import forecast_rain, ForecastUnavailable
    import pytest
    with pytest.raises(ForecastUnavailable):
        forecast_rain([80.15, 13.08, 80.20, 13.13], hours=6,
                      _fetch=lambda *a: (_ for _ in ()).throw(ConnectionError("down")))


def test_forecast_endpoint_503_offline(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    import app.services.rainfall_forecast as rf
    monkeypatch.setattr(rf, "_cache_path", lambda bbox, hours: __import__("pathlib").Path("/nonexistent-dir-xyz/c.json"))
    monkeypatch.setattr(rf, "_fetch_open_meteo", lambda *a: (_ for _ in ()).throw(ConnectionError("down")))
    c = TestClient(app)
    r = c.get("/api/forecast/rain?minLon=80.15&minLat=13.08&maxLon=80.20&maxLat=13.13&hours=6")
    assert r.status_code == 503
    assert "forecast-unavailable" in r.json()["detail"]
