def test_rainfall_variable():
    from app.models.simulation import Simulation
    sim=Simulation(name="var", area={"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"}, rainfall={"mode":"variable","totalTime":6,"maxRain":100,"unit":"rate","points":[{"time":0,"amount":0},{"time":3,"amount":80}]})
    assert sim.rainfall.mode=="variable"
    # backward compat
    sim2=Simulation(name="const", area={"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"}, rainfall={"rateMmHr":50,"durationHr":1})
    assert sim2.rainfall.mode=="constant"
    assert sim2.rainfall.constantRate==50

def test_rainfall_curve_on_create():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    r=c.post("/api/simulations", json={"name":"var","area":{"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"},"rainfall":{"mode":"variable","totalTime":6,"maxRain":100,"unit":"rate","points":[{"time":0,"amount":0},{"time":3,"amount":80}]}})
    assert r.status_code==201, r.text
    # Poll for curve if async
    import time
    sim=r.json()
    for _ in range(10):
        if sim["rainfall"].get("curve") and sim["rainfall"]["curve"].get("values"):
            break
        time.sleep(0.5)
        r2=c.get(f"/api/simulations/{sim['id']}")
        sim=r2.json()
    assert "curve" in sim["rainfall"] and sim["rainfall"]["curve"] is not None
    assert len(sim["rainfall"]["curve"]["values"]) > 0
