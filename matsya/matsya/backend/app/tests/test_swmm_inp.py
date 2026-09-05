def test_audit_flags_assumed_width():
    from app.services.engine.swmm_inp import audit_inputs
    drains = [{"id": "D1", "length_m": 120.0, "slope": 0.002}]
    r = audit_inputs(drains, {"rateMmHr": 50, "durationHr": 1})
    assert r["ready"] is True
    assert r["mode"] == "provisional-default-geometry"
    assert any("width" in a for a in r["assumed"])
    assert any("length" in o for o in r["observed"])

def test_audit_blocks_empty_drains():
    from app.services.engine.swmm_inp import audit_inputs
    r = audit_inputs([], {"rateMmHr": 50, "durationHr": 1})
    assert r["ready"] is False
    assert r["mode"] == "blocked-no-drains-in-bbox"

def test_build_inp_solves():
    from app.services.engine.swmm_inp import build_inp
    from pyswmm import Simulation
    drains = [{"id": "D1", "length_m": 100.0, "slope": 0.01, "z0": 10.0, "z1": 9.0}]
    p = build_inp(drains, {"rateMmHr": 50, "durationHr": 1}, [80.15, 13.08, 80.20, 13.13], "/tmp/t1.inp")
    with Simulation(p) as sim:
        for _ in sim:
            pass
    assert open(p.replace(".inp", ".rpt")).read().find("Analysis ended") > 0
