def test_elevation_on_create():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    r=c.post("/api/simulations", json={"name":"elev-create","area":{"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"},"rainfall":{"rateMmHr":50,"durationHr":1}})
    assert r.status_code==201, r.text
    sim=r.json()
    assert sim["elevation"] is not None, f"elevation is None: {sim}"
    assert sim["elevation"]["elevationUri"].endswith("/elevation"), sim["elevation"]
    assert sim["elevation"]["stats"]["min"] < sim["elevation"]["stats"]["max"], sim["elevation"]["stats"]
    # file exists — check via store base_path and legacy relative paths
    import pathlib
    sim_id=sim["id"]
    from app.services.simulation_store import store
    p_store = store.base_path / f"{sim_id}" / "elevation.png"
    p1 = pathlib.Path(f"matsya/matsya/backend/data/simulations/{sim_id}/elevation.png")
    p2 = pathlib.Path(f"backend/data/simulations/{sim_id}/elevation.png")
    p3 = pathlib.Path(f"data/simulations/{sim_id}/elevation.png")
    # also absolute double-nested fallback
    p_abs = pathlib.Path(__file__).resolve().parents[2] / "data" / "simulations" / f"{sim_id}" / "elevation.png"
    exists = p_store.exists() or p1.exists() or p2.exists() or p3.exists() or p_abs.exists()
    assert exists, f"elevation.png not found: store={p_store} p1={p1.resolve() if p1.exists() else p1} p2={p2.resolve() if p2.exists() else p2} p_abs={p_abs}"
    # also check elevation.json
    p_json = store.base_path / f"{sim_id}" / "elevation.json"
    assert p_json.exists() or (pathlib.Path(f"matsya/matsya/backend/data/simulations/{sim_id}/elevation.json")).exists() or pathlib.Path(f"backend/data/simulations/{sim_id}/elevation.json").exists(), "elevation.json missing"
    # fetch elevation
    r2=c.get(f"/api/simulations/{sim_id}/elevation")
    assert r2.status_code==200, f"{r2.status_code} {r2.text}"
    assert r2.headers["content-type"]=="image/png"
    assert r2.content[:8]==b"\x89PNG\r\n\x1a\n"
