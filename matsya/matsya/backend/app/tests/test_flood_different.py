def test_different_bbox_rainfall():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    r1=c.post("/api/simulations", json={"name":"flood-diff-1","area":{"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"},"rainfall":{"rateMmHr":50,"durationHr":1}})
    r2=c.post("/api/simulations", json={"name":"flood-diff-2","area":{"bbox":[80.25,13.00,80.30,13.05],"crs":"EPSG:4326"},"rainfall":{"rateMmHr":100,"durationHr":2}})
    assert r1.status_code==201 and r2.status_code==201
    sim1=r1.json()
    sim2=r2.json()
    # stats should differ
    assert sim1["flood"]["stats"]["maxDepth"] != sim2["flood"]["stats"]["maxDepth"] or sim1["flood"]["stats"]["floodedArea"] != sim2["flood"]["stats"]["floodedArea"]
    # PNG bytes should differ
    r1_png=c.get(f"/api/simulations/{sim1['id']}/flood?time=0")
    r2_png=c.get(f"/api/simulations/{sim2['id']}/flood?time=0")
    assert r1_png.content != r2_png.content
    assert r1_png.content[:8]==b"\x89PNG\r\n\x1a\n"
    # also test same bbox same rainfall should be similar (deterministic via seeded random) - not required but check not crash
