def test_sim_elevation():
    from app.models.simulation import Simulation
    sim=Simulation(name="elev", area={"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"}, rainfall={"rateMmHr":50,"durationHr":1}, elevation={"elevationUri":"/api/simulations/xxx/elevation","stats":{"min":4,"max":20}})
    assert sim.elevation.stats["min"]==4
    j=sim.model_dump()
    sim2=Simulation.model_validate(j)
    assert sim2.elevation.elevationUri.endswith("/elevation")
