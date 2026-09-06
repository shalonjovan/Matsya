def test_playback_steps_rule():
    from app.services.flood import _playback_steps, _playback_minutes_per_frame
    assert _playback_steps(1.0) == 6      # 10 min/frame
    assert _playback_steps(2.0) == 8      # 15 min/frame
    assert _playback_steps(6.0) == 24     # 15 min/frame
    assert _playback_steps(30.0) == 73    # capped
    assert _playback_steps(0) == 6        # floored
    assert abs(_playback_minutes_per_frame(2.0, 8) - 15.0) < 1e-9

def test_ensure_flood_writes_version_and_npy(tmp_path):
    from app.services.flood import ensure_flood
    import json, numpy as np
    from app.models.simulation import Simulation
    sim = Simulation.model_validate({"name": "pb", "area": {"bbox": [80.15, 13.08, 80.20, 13.13], "crs": "EPSG:4326"},
                                     "rainfall": {"rateMmHr": 100, "durationHr": 2}})
    ensure_flood(sim, width=10, height=10)
    from app.services.simulation_store import store
    fj = json.loads((store.base_path / sim.id / "flood" / "flood.json").read_text())
    assert fj["floodVersion"] == 2 and fj["steps"] == 8
    assert abs(fj["minutesPerFrame"] - 15.0) < 1e-9
    arr = np.load(store.base_path / sim.id / "flood" / "snapshots.npy")
    assert arr.shape == (8, 10, 10)

def test_frames_are_distinct():
    from app.services.flood import generate_flood
    import numpy as np
    snaps, _, _ = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 100, "durationHr": 2},
                                 width=10, height=10, steps=8)
    assert len(snaps) == 8
    assert not np.allclose(snaps[0], snaps[-1])

def test_stale_flood_heals_to_full_frames():
    import json, time
    from app.services.simulation_store import store
    from app.models.simulation import Simulation
    sim = Simulation.model_validate({"name": "stale", "area": {"bbox": [80.15, 13.08, 80.20, 13.13], "crs": "EPSG:4326"},
                                     "rainfall": {"rateMmHr": 50, "durationHr": 1}})
    store._save(sim)
    fj_path = store.base_path / sim.id / "flood" / "flood.json"
    fj_path.parent.mkdir(parents=True, exist_ok=True)
    fj_path.write_text(json.dumps({"maxDepth": 0.5, "steps": 3, "width": 10, "height": 10}))
    stats = None
    for _ in range(60):
        got = store.get(sim.id)
        f = getattr(got, "flood", None)
        s = (f.get("stats") if isinstance(f, dict) else getattr(f, "stats", None)) if f else None
        if isinstance(s, dict) and s.get("floodVersion") == 2:
            stats = s
            break
        time.sleep(2)
    assert stats is not None and stats["steps"] >= 6 and "minutesPerFrame" in stats

def test_point_labels_come_from_frames():
    from fastapi.testclient import TestClient
    from app.main import app
    import time as _t
    c = TestClient(app)
    r = c.post("/api/simulations", json={"name": "lbl", "area": {"bbox": [80.15, 13.08, 80.20, 13.13], "crs": "EPSG:4326"},
                                         "rainfall": {"rateMmHr": 100, "durationHr": 2}})
    assert r.status_code == 201
    sid = r.json()["id"]
    for _ in range(60):
        g = c.get(f"/api/simulations/{sid}").json()
        if (g.get("flood") or {}).get("stats", {}).get("minutesPerFrame"):
            break
        _t.sleep(2)
    p = c.get(f"/api/simulations/{sid}/point?lat=13.10&lon=80.17&time=0").json()
    assert p["floodDepth"] is not None
    # computed labels sit on the 15-min grid for this 2hr sim (statics were 00:05/01:20).
    # locate the wettest cell from the cached frames so the assertions bite.
    import numpy as _np
    from app.services.simulation_store import store as _store
    arr = _np.load(str(_store.base_path / sid / "flood" / "snapshots.npy"))
    ri, ci = _np.unravel_index(int(_np.argmax(arr[-1])), arr[-1].shape)
    minLon, minLat, maxLon, maxLat = (80.15, 13.08, 80.20, 13.13)
    la = maxLat - (ri + 0.5) * (maxLat - minLat) / arr.shape[1]
    lo = minLon + (ci + 0.5) * (maxLon - minLon) / arr.shape[2]
    assert float(arr[-1][ri, ci]) > 0.05
    target = c.get(f"/api/simulations/{sid}/point?lat={la}&lon={lo}&time=0").json()
    assert (target["floodDepth"] or 0) > 0.05
    assert target["firstFlooded"] is not None
    assert int(target["firstFlooded"].split(":")[1]) % 15 == 0
    if target["peak"]:
        assert int(target["peak"].split(":")[1]) % 15 == 0
