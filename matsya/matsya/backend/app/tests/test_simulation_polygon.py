def test_area_polygon():
    from app.models.simulation import Simulation
    poly = {"type":"Polygon","coordinates":[[[80.15,13.08],[80.20,13.08],[80.20,13.13],[80.15,13.13],[80.15,13.08]]]}
    sim=Simulation(name="poly", area={"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326","polygon":poly}, rainfall={"rateMmHr":50,"durationHr":1})
    assert sim.area.polygon["coordinates"][0][0]==[80.15,13.08]
    sim2=Simulation(name="poly2", area={"bbox":[80,13,81,14],"crs":"EPSG:4326","polygon":poly}, rainfall={"rateMmHr":50,"durationHr":1})
    assert sim2.area.polygon is not None

def test_area_polygon_invalid():
    from app.models.simulation import Simulation
    import pytest
    # not closed
    poly_bad = {"type":"Polygon","coordinates":[[[80.15,13.08],[80.20,13.08],[80.20,13.13],[80.15,13.13]]]}
    with pytest.raises(Exception):
        Simulation(name="bad", area={"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326","polygon":poly_bad}, rainfall={"rateMmHr":50,"durationHr":1})
