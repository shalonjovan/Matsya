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
