def test_simulation_roundtrip():
    from app.models.simulation import Simulation
    s=Simulation(name="Chennai Test", area={"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"}, rainfall={"rateMmHr":50,"durationHr":1})
    assert s.status=="Ready"
    j=s.model_dump()
    s2=Simulation.model_validate(j)
    assert s2.name=="Chennai Test"

def test_bbox_validation():
    from app.models.simulation import Simulation
    import pytest
    with pytest.raises(Exception):
        Simulation(name="bad", area={"bbox":[80.20,13.13,80.15,13.08],"crs":"EPSG:4326"}, rainfall={"rateMmHr":50,"durationHr":1})
