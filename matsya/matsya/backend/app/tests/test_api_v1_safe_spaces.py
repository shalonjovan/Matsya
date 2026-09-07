SIM = "72b53b60-54ad-4b1b-a500-378498b329c4"


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _origin(c):
    segs = c.get(f"/api/v1/simulations/{SIM}/roads/segments?limit=4000").json()["data"]["segments"]
    dry = [s for s in segs if s["peakCm"] < 15.0]
    assert dry, "seed sim has no dry segments"
    return dict(dry[0]["midpoint"])


def _post(c, origin=None, **kw):
    body = {"simId": SIM, "origin": dict(origin if origin is not None else _origin(c)),
            "departAtMin": 0, "thresholdCm": 15.0, "limit": 3}
    body.update(kw)
    return c.post("/api/v1/safe-spaces", json=body)


def test_safe_spaces_shape_and_order():
    c = _client()
    r = _post(c)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["v"] == "1"
    spaces = j["data"]["spaces"]
    assert 1 <= len(spaces) <= 3
    for i, s in enumerate(spaces):
        assert {"rank", "kind", "name", "lat", "lon", "elevationM", "peakCm", "route"} <= set(s)
        assert s["rank"] == i + 1
        assert s["kind"] in ("road", "ground")
        assert s["peakCm"] < 15.0
        assert s["route"]["etaMin"] >= 0
        assert s["route"]["path"][0][0] == s["route"]["path"][0][0]  # lon-first pairs
        assert len(s["route"]["path"][0]) == 2
    etas = [s["route"]["etaMin"] for s in spaces]
    assert etas == sorted(etas)


def test_safe_spaces_unknown_sim_404():
    c = _client()
    r = c.post("/api/v1/safe-spaces", json={
        "simId": "00000000-0000-0000-0000-000000000000",
        "origin": {"lat": 13.10, "lon": 80.19}})
    assert r.status_code == 404


def test_safe_spaces_far_origin_422():
    c = _client()
    r = _post(c, origin={"lat": 0.0, "lon": 0.0})
    assert r.status_code == 422


def test_safe_spaces_deterministic():
    c = _client()
    a = _post(c).json()["data"]["spaces"]
    b = _post(c).json()["data"]["spaces"]
    assert [(s["name"], s["route"]["etaMin"]) for s in a] == [(s["name"], s["route"]["etaMin"]) for s in b]


def test_safe_spaces_snaps_distant_origin_with_disclosure():
    # fixed gap point (~230m from mapped roads): beyond 200m snap, inside 2km fallback
    c = _client()
    r = _post(c, origin={"lat": 13.11, "lon": 80.182})
    assert r.status_code == 200, r.text
    j = r.json()["data"]
    assert j["originSnapped"] is not None
    assert 200 < j["originSnapped"]["distanceM"] < 2000
    assert 1 <= len(j["spaces"]) <= 3


def test_safe_spaces_far_field_422():
    # mid-ocean: beyond even the fallback radius
    c = _client()
    r = _post(c, origin={"lat": 5.0, "lon": 75.0})
    assert r.status_code == 422
    assert "2 km" in r.json()["detail"]
