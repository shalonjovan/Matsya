def test_point_floodDepth():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.flood import generate_flood
    import math

    c = TestClient(app)
    r = c.post(
        "/api/simulations",
        json={
            "name": "point-flood",
            "area": {"bbox": [80.15, 13.08, 80.20, 13.13], "crs": "EPSG:4326"},
            "rainfall": {"rateMmHr": 50, "durationHr": 1},
        },
    )
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    # wait for async bg flood generation (coupled model slower than old bathtub)
    import time as _t
    sj = {}
    for _ in range(45):
        g = c.get(f"/api/simulations/{sid}")
        try:
            sj = g.json()
        except Exception:
            sj = {}
        if sj.get("flood") is not None and (sj.get("flood") or {}).get("stats"):
            break
        _t.sleep(2)
    bbox = [80.15, 13.08, 80.20, 13.13]
    rainfall = {"rateMmHr": 50, "durationHr": 1}
    # reference must use the sim's stored step count (duration-derived frames)
    _nsteps = ((sj.get("flood") or {}).get("stats") or {}).get("steps", 3) or 3
    snaps, _, stats = generate_flood(bbox, rainfall, width=180, height=180, steps=_nsteps)

    def latLonToRowCol(lat, lon, bbox, rows, cols):
        minLon, minLat, maxLon, maxLat = bbox
        dy = (maxLat - minLat) / rows
        dx = (maxLon - minLon) / cols
        rr = math.floor((maxLat - lat) / dy)
        cc = math.floor((lon - minLon) / dx)
        rr = max(0, min(rows - 1, rr))
        cc = max(0, min(cols - 1, cc))
        return rr, cc

    # Check point 1
    r = c.get(f"/api/simulations/{sid}/point?lat=13.10&lon=80.17&time=0")
    assert r.status_code == 200, r.text
    j = r.json()
    r2 = c.get(f"/api/simulations/{sid}/point?lat=13.12&lon=80.18&time=0")
    assert r2.status_code == 200, r2.text
    j2 = r2.json()

    # Original spec check: mock was 0.42 (illustrative). Ensure not both exactly mock.
    # Compute hash mocks for these points at time=0
    h1 = (int(13.10 * 1000) ^ int(80.17 * 1000)) % 100
    mock1 = (h1 / 100) * 0.3
    h2 = (int(13.12 * 1000) ^ int(80.18 * 1000)) % 100
    mock2 = (h2 / 100) * 0.3
    # Real flood should not equal hash mock for at least one point, and should equal sampled flood array
    rr1, cc1 = latLonToRowCol(13.10, 80.17, bbox, 180, 180)
    rr2, cc2 = latLonToRowCol(13.12, 80.18, bbox, 180, 180)
    expected1 = float(snaps[0][rr1, cc1])
    expected2 = float(snaps[0][rr2, cc2])

    # Assert floodDepth matches real flood array (not hash mock)
    assert abs(j["floodDepth"] - expected1) < 1e-6, f"floodDepth {j['floodDepth']} != expected {expected1} mock {mock1}"
    assert abs(j2["floodDepth"] - expected2) < 1e-6, f"floodDepth2 {j2['floodDepth']} != expected {expected2} mock {mock2}"

    # Also check spec's illustrative 0.42 check (should pass after fix, and would have been fragile before)
    assert j["floodDepth"] != 0.42 or j2["floodDepth"] != 0.42

    # If expected differs from mock, ensure response is not mock (ensures failure before fix)
    if abs(expected1 - mock1) > 1e-6:
        assert abs(j["floodDepth"] - mock1) > 1e-6, f"still mock {j['floodDepth']} == {mock1}"
    if abs(expected2 - mock2) > 1e-6:
        assert abs(j2["floodDepth"] - mock2) > 1e-6

    # Check time progression: flood should increase with time step for low spot
    import numpy as np

    diff = snaps[2] - snaps[0]
    idx = np.argwhere(diff > 0.05)
    if len(idx) > 0:
        ri, ci = idx[0]
        minLon, minLat, maxLon, maxLat = bbox
        dy = (maxLat - minLat) / 180
        dx = (maxLon - minLon) / 180
        lat = maxLat - (ri + 0.5) * dy
        lon = minLon + (ci + 0.5) * dx
        r0 = c.get(f"/api/simulations/{sid}/point?lat={lat}&lon={lon}&time=0")
        r2p = c.get(f"/api/simulations/{sid}/point?lat={lat}&lon={lon}&time=2")
        assert r0.status_code == 200 and r2p.status_code == 200
        assert r2p.json()["floodDepth"] > r0.json()["floodDepth"], f"time 2 {r2p.json()['floodDepth']} should be > time 0 {r0.json()['floodDepth']}"
