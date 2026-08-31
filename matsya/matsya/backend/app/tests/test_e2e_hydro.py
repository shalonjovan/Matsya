def test_e2e_hydro_flow():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    # create simulation
    r=c.post("/api/simulations", json={"name":"e2e-hydro","area":{"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"},"rainfall":{"rateMmHr":50,"durationHr":1}})
    assert r.status_code==201
    sid=r.json()["id"]
    # check hydro summary
    r=c.get("/api/hydro/summary")
    assert r.status_code==200
    assert r.json()["snapped_to_waterbody"] == 20
    # run coupled
    r=c.post(f"/api/simulations/{sid}/run")
    assert r.status_code==202
    # check hydro graph
    r=c.get("/api/hydro/graph")
    assert r.status_code==200
    assert len(r.json()["drains"]["features"])==52
    # check point still works
    r=c.get(f"/api/simulations/{sid}/point?lat=13.10&lon=80.17&time=0")
    assert r.status_code==200
    # check report has hydro
    r=c.get(f"/api/simulations/{sid}/report")
    assert r.status_code==200
    assert "hydro" in r.json() or "floodStats" in r.json()
