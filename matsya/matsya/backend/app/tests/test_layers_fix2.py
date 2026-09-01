def test_layers_drains():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    r=c.get("/api/layers/drains?limit=10")
    assert r.status_code==200
    j=r.json()
    assert len(j["features"]) == 10
    assert j["total"] == 10276  # actual is 10276

def test_layers_waterbodies():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    r=c.get("/api/layers/waterbodies?limit=5")
    assert r.status_code==200
    j=r.json()
    assert len(j["features"]) == 5
    assert j["total"] == 4086

def test_hydro_still_52():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    r=c.get("/api/hydro/graph")
    assert r.status_code==200
    assert len(r.json()["drains"]["features"]) == 52
