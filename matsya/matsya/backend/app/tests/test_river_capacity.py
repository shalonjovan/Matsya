def test_manning_bankfull_sanity():
    from app.services.hydro.river_capacity import reach_capacity
    r = reach_capacity(2000.0, 0.001, width_m=10.0, depth_m=2.0)
    # hand calc: A=(10+2)*2/2? trapezoidal 1:1: A=d*(w+d)=2*12=24; P=w+2*d*sqrt2=15.66; R=1.533
    # Q=(1/0.035)*24*1.533^0.667*sqrt(0.001) ~= 28.57*24*1.329*0.0316 ~= 28.8
    assert 20.0 < r["qbank"] < 40.0
    assert "assumed" in r["source"] or r["source"] == "observed-dims"

def test_defaults_flagged():
    from app.services.hydro.river_capacity import reach_capacity
    r = reach_capacity(800.0, 0.001)
    assert r["width_m"] == 5.0 and r["depth_m"] == 1.5 and r["source"] == "assumed-defaults"
    assert r["qbank"] > 0

def test_valley_width_on_synthetic_v():
    import numpy as np
    from app.services.hydro.river_capacity import valley_width
    dem = np.abs(np.arange(-90, 90).reshape(1, -1).repeat(10, 0)).astype(float)  # V valley, min at col 90
    w, src = valley_width(dem, [0, 0, 1, 1], 180, 10, [(0.4, 0.5), (0.6, 0.5)])
    assert w is not None and 3.0 <= w <= 80.0

def test_build_reaches_real_assets():
    from app.services.hydro.river_capacity import build_reaches
    reaches = build_reaches([80.15, 13.08, 80.20, 13.13], max_n=10)
    assert 1 <= len(reaches) <= 10
    for r in reaches:
        assert r["qbank"] > 0 and r["length_m"] > 0
        assert r["source"] in ("observed-valley", "assumed-defaults", "observed-dims")
