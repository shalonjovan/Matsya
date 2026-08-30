def test_matsya_package():
    from app.services.package_service import create_matsya, read_matsya
    from app.models.simulation import Simulation
    sim=Simulation(name="pkg", area={"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"}, rainfall={"rateMmHr":50,"durationHr":1})
    b=create_matsya(sim)
    sim2=read_matsya(b)
    assert sim2.name=="pkg"

def test_matsya_missing():
    from app.services.package_service import read_matsya
    import pytest, zipfile, io
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z: z.writestr("metadata.json","{}")
    buf.seek(0)
    with pytest.raises(ValueError): read_matsya(buf.read())

def test_package_api():
    from fastapi.testclient import TestClient
    from app.main import app
    c=TestClient(app)
    r=c.post("/api/simulations", json={"name":"pkg-api","area":{"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"},"rainfall":{"rateMmHr":50,"durationHr":1}})
    sid=r.json()["id"]
    r=c.get(f"/api/simulations/{sid}/export")
    assert r.status_code==200
    assert r.headers["content-type"]=="application/octet-stream"
    # import
    import io
    files={"file": ("test.matsya", r.content, "application/octet-stream")}
    r=c.post("/api/simulations/import", files=files)
    assert r.status_code==201
