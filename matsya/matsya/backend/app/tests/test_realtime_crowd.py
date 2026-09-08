import shutil


def _clean():
    from app.services.simulation_store import store
    from app.services.realtime.manager import REALTIME_ID
    try:
        store.delete(REALTIME_ID)
    except Exception:
        pass
    try:
        shutil.rmtree(store.base_path / REALTIME_ID, ignore_errors=True)
    except Exception:
        pass


def _realtime():
    from app.services.realtime.manager import tick
    _clean()
    tick()
    from app.services.realtime.manager import REALTIME_ID
    return REALTIME_ID


def test_crowd_report_validated():
    from fastapi.testclient import TestClient
    from app.main import app
    _realtime()
    try:
        c = TestClient(app)
        assert c.post("/api/v1/crowd/reports", json={"lat": 0.0, "lon": 0.0, "depthCm": 50}).status_code == 422
        assert c.post("/api/v1/crowd/reports", json={"lat": 13.10, "lon": 80.17, "depthCm": 5000}).status_code == 422
        r = c.post("/api/v1/crowd/reports", json={"lat": 13.10, "lon": 80.17, "depthCm": 50, "kind": "flooded", "note": "ankle deep"})
        assert r.status_code == 201, r.text
        assert "reportId" in r.json()["data"]
        g = c.get("/api/v1/crowd/reports")
        assert g.status_code == 200
        assert any(rep["depthCm"] == 50 for rep in g.json()["data"]["reports"])
    finally:
        _clean()


def test_crowd_overlay_raises_cell():
    import numpy as np
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.simulation_store import store
    from app.services.realtime.manager import REALTIME_ID, apply_crowd_overlay
    _realtime()
    try:
        c = TestClient(app)
        c.post("/api/v1/crowd/reports", json={"lat": 13.10, "lon": 80.17, "depthCm": 200, "kind": "drain"})
        d = apply_crowd_overlay(REALTIME_ID)
        assert d["applied"] >= 1
        from app.services.snapshots import load_snapshots
        snaps, _, _ = load_snapshots(store.get(REALTIME_ID))
        assert float(np.asarray(snaps[-1]).max()) >= 1.0  # 200cm pin visible allowing decay
    finally:
        _clean()


def test_report_applies_immediately():
    import numpy as np
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.simulation_store import store
    from app.services.realtime.manager import REALTIME_ID
    from app.services.snapshots import load_snapshots
    from app.services.analysis import _lat_lon_to_row_col
    _realtime()
    try:
        c = TestClient(app)
        r = c.post("/api/v1/crowd/reports", json={"lat": 13.10, "lon": 80.17, "depthCm": 200, "kind": "flooded"})
        assert r.status_code == 201, r.text
        snaps, _, bbox = load_snapshots(store.get(REALTIME_ID))
        arr = np.asarray(snaps[-1])
        rr, cc = _lat_lon_to_row_col(13.10, 80.17, list(bbox), *arr.shape)
        assert float(arr[rr, cc]) >= 1.0  # visible without waiting for next tick
    finally:
        _clean()


def test_zero_report_clears_cell():
    import numpy as np
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.simulation_store import store
    from app.services.realtime.manager import REALTIME_ID
    from app.services.snapshots import load_snapshots
    from app.services.analysis import _lat_lon_to_row_col
    _realtime()
    try:
        c = TestClient(app)
        assert c.post("/api/v1/crowd/reports", json={"lat": 13.10, "lon": 80.17, "depthCm": 200, "kind": "flooded"}).status_code == 201
        assert c.post("/api/v1/crowd/reports", json={"lat": 13.10, "lon": 80.17, "depthCm": 0, "kind": "flooded"}).status_code == 201
        snaps, _, bbox = load_snapshots(store.get(REALTIME_ID))
        arr = np.asarray(snaps[-1])
        rr, cc = _lat_lon_to_row_col(13.10, 80.17, list(bbox), *arr.shape)
        assert float(arr[rr, cc]) == 0.0  # authoritative dry observation wins
    finally:
        _clean()
