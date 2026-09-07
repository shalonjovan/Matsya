SIM = "72b53b60-54ad-4b1b-a500-378498b329c4"


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _midpoints(c, limit=60):
    segs = c.get(f"/api/v1/simulations/{SIM}/roads/segments?limit={limit}").json()["data"]["segments"]
    assert len(segs) >= 10
    return segs


def test_dry_route_between_same_road_segments():
    import pytest
    c = _client()
    segs = _midpoints(c)
    by_road = {}
    for s in segs:
        by_road.setdefault(s["roadId"], []).append(s)
    pair = next((v[:2] for v in by_road.values() if len(v) >= 2), None)
    if pair is None:
        pytest.skip("no multi-segment road in feed")
    a, b = pair[0]["midpoint"], pair[1]["midpoint"]
    r = c.post("/api/v1/routes/safe", json={
        "origin": a, "destination": b,
        "departAtMin": 0, "simId": SIM, "thresholdCm": 10000.0})
    assert r.status_code == 200, r.text
    j = r.json()["data"]
    assert j["fastest"] is not None and j["fastest"]["etaMin"] > 0
    assert j["fastest"]["path"][0][0] == pytest.approx(a["lon"], abs=0.003)  # lon-first, snapped
    assert j["fastest"]["path"][0][1] == pytest.approx(a["lat"], abs=0.003)


def test_flooded_route_reroutes_dry():
    c = _client()
    segs = _midpoints(c)
    mids = [s["midpoint"] for s in segs]
    hit = None
    for i in range(6):
        for j in range(i + 1, 12):
            r = c.post("/api/v1/routes/safe", json={
                "origin": mids[i], "destination": mids[j],
                "departAtMin": 0, "simId": SIM, "thresholdCm": 15.0}).json()["data"]
            f, s = r["fastest"], r["safest"]
            if f and s and f["maxDepthCm"] >= 15.0 and s["maxDepthCm"] < 15.0 \
                    and len(s["avoidedSegments"]) > 0:
                hit = (f, s)
                break
        if hit:
            break
    assert hit is not None, "no reroute found among candidate pairs"
    f, s = hit
    assert s["floodDelayMin"] >= 0.0


def test_zero_threshold_cuts_off_honestly():
    c = _client()
    segs = _midpoints(c)
    a, b = segs[0]["midpoint"], segs[4]["midpoint"]
    r = c.post("/api/v1/routes/safe", json={
        "origin": a, "destination": b,
        "departAtMin": 0, "simId": SIM, "thresholdCm": 0.0})
    assert r.status_code == 200, r.text
    j = r.json()["data"]
    if j["safest"] is not None:
        assert j["safest"]["maxDepthCm"] == 0.0
    else:
        assert j["reason"]  # cut off: honest reason, still HTTP 200


def test_far_origin_422():
    c = _client()
    r = c.post("/api/v1/routes/safe", json={
        "origin": {"lat": 0.0, "lon": 0.0}, "destination": {"lat": 13.11, "lon": 80.20},
        "departAtMin": 0, "simId": SIM})
    assert r.status_code == 422
