def test_sim_flood():
    from app.models.simulation import Simulation
    sim=Simulation(name="flood", area={"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"}, rainfall={"rateMmHr":50,"durationHr":1}, flood={"floodUri":"/api/simulations/xxx/flood?time=0","stats":{"maxDepth":0.5}})
    assert sim.flood.stats["maxDepth"]==0.5
    j=sim.model_dump()
    sim2=Simulation.model_validate(j)
    assert sim2.flood.floodUri.endswith("/flood?time=0")
