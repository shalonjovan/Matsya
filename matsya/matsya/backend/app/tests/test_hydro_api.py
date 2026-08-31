def test_hydro_summary():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    r=c.get("/api/hydro/summary")
    assert r.status_code==200
    j=r.json()
    assert j["snapped_to_waterbody"] > 5
    assert j["drains"] == 52
    assert j["waterbodies"] >= 3000

def test_hydro_graph():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    r=c.get("/api/hydro/graph")
    assert r.status_code==200
    j=r.json()
    assert "drains" in j
    assert "waterbodies" in j
    assert len(j["drains"]["features"]) == 52
    # check target property exists
    assert "target" in j["drains"]["features"][0]["properties"]

def test_hydro_check():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    r=c.get("/api/hydro/check")
    assert r.status_code==200
    j=r.json()
    assert j["valid"] == True or j["unsnapped"] < 5
    assert "snapped_to_waterbody" in j

def test_hydro_waterbodies():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    r=c.get("/api/hydro/waterbodies?limit=5")
    assert r.status_code==200
    j=r.json()
    assert len(j)==5
    assert "area_m2" in j[0]
    assert "spill_crest" in j[0]

def test_sim_hydro():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    # create sim
    r=c.post("/api/simulations", json={"name":"hydro-test","area":{"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"},"rainfall":{"rateMmHr":50,"durationHr":1}})
    sid=r.json()["id"]
    r=c.get(f"/api/simulations/{sid}/hydro")
    assert r.status_code==200
    j=r.json()
    assert "waterbody_levels" in j
