def test_dem_sample():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    r=c.get("/api/dem/sample?lon=80.17&lat=13.08")
    assert r.status_code==200
    j=r.json()
    assert "elevation" in j
    assert j["elevation"] is not None
    assert -10 < j["elevation"] < 100

def test_dem_sample_ocean():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    r=c.get("/api/dem/sample?lon=80.5&lat=13.0")
    assert r.status_code==200
    j=r.json()
    # ocean may be None or value, but should not crash
    assert "elevation" in j
