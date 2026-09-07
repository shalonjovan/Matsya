CELL = {"amount": 120.0, "unit": "rate",
        "polygon": {"type": "Polygon", "coordinates": [[[80.16, 13.09], [80.17, 13.09], [80.17, 13.10], [80.16, 13.10], [80.16, 13.09]]]}}


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_nowcast_creates_zoned_sim():
    c = _client()
    r = c.post("/api/v1/nowcasts", json={
        "name": "radar-001", "bbox": [80.15, 13.08, 80.20, 13.13],
        "issuedAt": "2026-09-08T06:00:00+05:30", "cells": [dict(CELL)]})
    assert r.status_code == 201, r.text
    j = r.json()["data"]
    assert j["acceptedCells"] == 1 and j["droppedCells"] == []
    sim = c.get(f"/api/simulations/{j['simId']}").json()
    assert len(sim["rainfall"]["zones"]) == 1
    # cleanup so the store is not polluted for other suites
    c.delete(f"/api/simulations/{j['simId']}")


def test_nowcast_caps_cells_at_12():
    c = _client()
    cells = []
    for i in range(13):
        _c = {"id": f"r{i}", "amount": 10.0, "unit": "rate", "polygon": CELL["polygon"]}
        cells.append(_c)
    r = c.post("/api/v1/nowcasts", json={
        "name": "radar-013", "bbox": [80.15, 13.08, 80.20, 13.13],
        "issuedAt": "2026-09-08T06:00:00+05:30", "cells": cells})
    assert r.status_code == 201, r.text
    j = r.json()["data"]
    assert j["acceptedCells"] == 12 and len(j["droppedCells"]) == 1
    c.delete(f"/api/simulations/{j['simId']}")
