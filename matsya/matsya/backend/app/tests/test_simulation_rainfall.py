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
    assert "curve" in r.json()["rainfall"]
    assert len(r.json()["rainfall"]["curve"]["values"]) > 0
