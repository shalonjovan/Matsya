SIM = "72b53b60-54ad-4b1b-a500-378498b329c4"


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_drainage_nodes_shape():
    c = _client()
    r = c.get(f"/api/v1/simulations/{SIM}/drainage/nodes")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["v"] == "1"
    assert isinstance(j["data"]["nodes"], list) and len(j["data"]["nodes"]) >= 1
    n = j["data"]["nodes"][0]
    assert {"id", "surcharged", "capacityUsedPct"} <= set(n)
    assert n.get("capacity", None) is None or "capacity" not in n  # section 15: never invent
    assert "source" in j["data"]


def test_drainage_nodes_unknown_sim_404():
    c = _client()
    r = c.get("/api/v1/simulations/00000000-0000-0000-0000-000000000000/drainage/nodes")
    assert r.status_code == 404


def test_alerts_match_segments():
    c = _client()
    segs = c.get(f"/api/v1/simulations/{SIM}/roads/segments?limit=4000").json()["data"]["segments"]
    flooded = {s["segmentId"] for s in segs if not s["series"][0]["passable"]}
    alerts = c.get(f"/api/v1/alerts?simId={SIM}").json()["data"]
    assert set(alerts["floodedNow"]) == flooded
    assert all({"segmentId", "etaMin"} <= set(w) for w in alerts["floodingWithinMin"])
