from fastapi.testclient import TestClient
from app.main import app
def test_crud():
    c=TestClient(app)
    r=c.post("/api/simulations", json={"name":"W1","area":{"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"},"rainfall":{"rateMmHr":50,"durationHr":1}})
    assert r.status_code==201
    sid=r.json()["id"]
    r=c.get(f"/api/simulations/{sid}")
    assert r.json()["name"]=="W1"
    r=c.patch(f"/api/simulations/{sid}", json={"name":"W1-renamed"})
    assert r.json()["name"]=="W1-renamed"
    r=c.post(f"/api/simulations/{sid}/duplicate", json={"name":"W1-copy"})
    assert r.status_code==201
    assert r.json()["name"]=="W1-copy"
    r=c.get("/api/simulations")
    assert len(r.json())>=2
    r=c.delete(f"/api/simulations/{sid}")
    assert r.status_code==204
