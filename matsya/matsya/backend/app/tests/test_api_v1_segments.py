SIM = "72b53b60-54ad-4b1b-a500-378498b329c4"


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _sim_or_skip(c):
    r = c.get(f"/api/simulations/{SIM}")
    if r.status_code == 404:
        import pytest
        pytest.skip("seed sim missing from store")


def test_segments_envelope_and_shape():
    c = _client()
    _sim_or_skip(c)
    r = c.get(f"/api/v1/simulations/{SIM}/roads/segments?limit=5")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["v"] == "1" and j["generatedAt"] and "disclaimer" in j
    segs = j["data"]["segments"]
    assert len(segs) == 5
    s = segs[0]
    assert {"segmentId", "roadId", "name", "midpoint", "lengthM", "peakCm", "series"} <= set(s)
    assert all({"t", "depthCm", "passable"} <= set(p) for p in s["series"])


def test_segments_unknown_sim_404():
    c = _client()
    r = c.get("/api/v1/simulations/00000000-0000-0000-0000-000000000000/roads/segments")
    assert r.status_code == 404


def test_segments_stable_ids():
    c = _client()
    _sim_or_skip(c)
    a = c.get(f"/api/v1/simulations/{SIM}/roads/segments?limit=10").json()["data"]["segments"]
    b = c.get(f"/api/v1/simulations/{SIM}/roads/segments?limit=10").json()["data"]["segments"]
    assert [s["segmentId"] for s in a] == [s["segmentId"] for s in b]
