def test_package_flood():
    from app.models.simulation import Simulation
    from app.services.package_service import create_matsya
    import io, zipfile
    sim=Simulation(name="pkg-flood", area={"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"}, rainfall={"rateMmHr":50,"durationHr":1}, flood={"floodUri":"/api/simulations/test/flood?time=0","stats":{"maxDepth":0.5}})
    b=create_matsya(sim)
    z=zipfile.ZipFile(io.BytesIO(b))
    namelist = z.namelist()
    # explicit flood checks per spec §6
    assert "flood/flood.json" in namelist, f"missing flood/flood.json in {namelist}"
    assert "flood/0.png" in namelist, f"missing flood/0.png in {namelist}"
    assert any("flood" in name for name in namelist)

def test_package_flood_roundtrip():
    from app.models.simulation import Simulation
    from app.services.package_service import create_matsya, read_matsya
    sim=Simulation(name="pkg-flood2", area={"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"}, rainfall={"rateMmHr":50,"durationHr":1}, flood={"floodUri":"/api/simulations/test/flood?time=0","stats":{"maxDepth":0.8, "floodedArea":1.2}, "width":180, "height":180, "steps":3})
    b=create_matsya(sim)
    sim2=read_matsya(b)
    assert sim2.flood is not None
    assert sim2.flood.stats["maxDepth"] == 0.8
    assert sim2.flood.floodUri == "/api/simulations/test/flood?time=0"
