def test_flood_on_create():
    from fastapi.testclient import TestClient
    from app.main import app
    import time
    c=TestClient(app)
    r=c.post("/api/simulations", json={"name":"flood-create","area":{"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"},"rainfall":{"rateMmHr":50,"durationHr":1}})
    assert r.status_code==201
    sim=r.json()
    sim_id = sim["id"]
    # bg elevation/flood generation is async (coupled D8+storage takes ~10-20s); poll
    for _ in range(45):
        g = c.get(f"/api/simulations/{sim_id}")
        assert g.status_code == 200
        sim = g.json()
        if sim.get("flood") is not None and (sim["flood"] or {}).get("stats"):
            break
        time.sleep(2)
    assert sim["flood"] is not None
    assert sim["flood"]["floodUri"].endswith("/flood?time=0") or sim["flood"]["floodUri"].endswith("/flood")
    assert sim["flood"]["stats"]["maxDepth"] > 0
    import pathlib
    sim_id=sim["id"]
    from app.services.simulation_store import store
    p = store.base_path / f"{sim_id}" / "flood" / "0.png"
    # also check legacy double-nested path
    assert p.exists() or pathlib.Path(f"matsya/matsya/backend/data/simulations/{sim_id}/flood/0.png").exists() or pathlib.Path(f"backend/data/simulations/{sim_id}/flood/0.png").exists()
    # fetch flood
    r2=c.get(f"/api/simulations/{sim_id}/flood?time=0")
    assert r2.status_code==200
    assert r2.headers["content-type"]=="image/png"
