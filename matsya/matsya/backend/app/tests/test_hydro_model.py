def test_hydro_roundtrip():
    from app.models.simulation import Simulation
    sim = Simulation(
        name="hydro test",
        area={"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"},
        rainfall={"rateMmHr":50,"durationHr":1},
        hydro={"enabled": True, "version":"1.1", "drainToWaterbody":{"0":"wb:1"}, "waterbodyStates":{"1":{"stage":5.2}}}
    )
    assert sim.hydro.enabled == True
    assert sim.hydro.version == "1.1"
    j = sim.model_dump()
    sim2 = Simulation.model_validate(j)
    assert sim2.hydro.enabled == True
    assert sim2.hydro.drainToWaterbody["0"] == "wb:1"

def test_hydro_default():
    from app.models.simulation import Simulation
    sim = Simulation(name="no hydro", area={"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"}, rainfall={"rateMmHr":50,"durationHr":1})
    assert sim.hydro is None
    # also test with hydro disabled
    sim2 = Simulation(name="disabled", area={"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"}, rainfall={"rateMmHr":50,"durationHr":1}, hydro={"enabled":False})
    assert sim2.hydro.enabled == False
