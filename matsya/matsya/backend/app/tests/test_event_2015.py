def test_fixture_loads_with_sources():
    from app.services.event_2015 import load_fixture
    f = load_fixture()
    assert f["release"]["cusecs"] == 29000 and f["release"]["modeled"] is False
    assert any(s["mm24h"] == 494 for s in f["rainfallStations"])
    assert all("source" in loc for loc in f["referenceLocalities"])


def test_event_sim_matches_dec1_totals():
    from app.services.event_2015 import build_event_sim
    from app.services.simulation_store import store
    sim = build_event_sim()
    try:
        _rf = sim["rainfall"] if isinstance(sim, dict) else sim.rainfall
        zones = _rf["zones"] if isinstance(_rf, dict) else _rf.zones
        assert zones is not None and len(zones) == 2
        def _amt(z):
            _z = z if isinstance(z, dict) else z.model_dump(mode="json")
            if str(_z.get("mode", "constant")) == "variable":
                return float(_z.get("maxRain", 0.0))
            return float(_z.get("amount", 0.0))
        totals = sorted(_amt(z) for z in zones)
        assert totals == [300.0, 490.0]
        _bb = sim["area"]["bbox"] if isinstance(sim, dict) else sim.area.bbox
        assert _bb[1] >= 13.0  # in DEM tile
    finally:
        try:
            store.delete(sim["id"] if isinstance(sim, dict) else sim.id)
        except Exception:
            pass


def test_compare_shape_and_honesty():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.event_2015 import build_event_sim
    from app.services.simulation_store import store
    sim = build_event_sim("comparetest")
    sid = None
    try:
        sid = sim["id"] if isinstance(sim, dict) else sim.id
        import time
        for _ in range(150):
            s = store.get(sid)
            if isinstance(s, dict):
                st = s.get("status")
            else:
                st = s.status
            st = str(getattr(st, "value", st))
            if st == "Completed":
                break
            time.sleep(2)
        c = TestClient(app)
        r = c.get(f"/api/v1/event/2015/compare?simId={sid}")
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert {"localities", "recall", "bandAgreement", "similarityPct", "formula"} <= set(d)
        assert 0 <= d["similarityPct"] <= 100
        assert all("reportedBand" in loc and "modeledBand" in loc for loc in d["localities"])
    finally:
        try:
            if sid:
                store.delete(sid)
        except Exception:
            pass
