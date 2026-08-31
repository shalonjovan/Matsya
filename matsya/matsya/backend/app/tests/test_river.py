def test_river():
    from app.services.hydro.river import RiverReach
    r=RiverReach(length=2000, slope=0.001)
    out1=r.route(10, 300)
    # first step with 0 prev, should be attenuated (<10)
    assert out1 < 10
    assert out1 >= 0
    # second step with sustained inflow, should increase but still <10? Actually with Muskingum it will ramp
    out2=r.route(10, 300)
    assert out2 > out1
    assert out2 < 10 or abs(out2-10) < 1
    # after many steps, should approach inflow
    for _ in range(5):
        out=r.route(10, 300)
    assert abs(out - 10) < 2

def test_river_zero():
    from app.services.hydro.river import RiverReach
    r=RiverReach()
    assert r.route(0,300)==0
    assert r.route(0,300)==0
