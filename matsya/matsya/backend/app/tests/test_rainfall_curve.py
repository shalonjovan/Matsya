def test_interpolate_rate():
    from app.services.rainfall_curve import interpolate
    points=[{"time":0,"amount":0},{"time":1,"amount":50},{"time":2,"amount":20}]
    res=interpolate(points, totalTime=2, maxRain=100, unit="rate", steps=4)
    assert len(res["values"])==4
    assert 0 <= min(res["values"]) <= max(res["values"]) <= 100
    assert res["values"][0]==0
    assert 40 < res["values"][2] < 60

def test_interpolate_total_to_rate():
    from app.services.rainfall_curve import interpolate
    points=[{"time":0,"amount":0},{"time":1,"amount":30},{"time":2,"amount":60}]
    res=interpolate(points, totalTime=2, maxRain=100, unit="total", steps=4)
    assert 20 < res["values"][2] < 40

def test_random():
    from app.services.rainfall_curve import random_preset
    for t in ["burst","gradual","double-peak","random"]:
        pts=random_preset(t, totalTime=6, maxRain=100, unit="rate")
        assert len(pts)>=4
        assert all(0<=p["time"]<=6 and 0<=p["amount"]<=100 for p in pts)
        assert pts==sorted(pts, key=lambda x: x["time"])
        if t=="burst": assert pts[1]["amount"] > pts[-1]["amount"]
