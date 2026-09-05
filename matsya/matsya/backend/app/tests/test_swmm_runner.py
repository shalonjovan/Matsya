import time

def _drains():
    return [
        {"id": "D1", "length_m": 100.0, "slope": 0.01, "z0": 10.0, "z1": 9.0},
        {"id": "D2", "length_m": 100.0, "slope": 0.01, "z0": 10.0, "z1": 9.0},
    ]

def test_runner_completes_with_real_stats():
    from app.services.engine import swmm_runner as eng
    sim = {"id": "s1", "area": {"bbox": [80.15, 13.08, 80.20, 13.13]},
           "rainfall": {"rateMmHr": 50, "durationHr": 1},
           "_test_drains": _drains()}
    rid = eng.run_simulation("s1", sim)
    for _ in range(60):
        r = eng.get_run(rid)
        if r["status"] in ("Completed", "Failed"):
            break
        time.sleep(2)
    assert r["status"] == "Completed", r
    assert r["results"]["stats"]["solved"] is True
    assert r["engine"] == "swmm"

def test_choked_network_floods():
    from app.services.engine import swmm_runner as eng
    import app.services.engine.swmm_inp as inp
    old_w, old_d = inp.WIDTH_M, inp.DEPTH_M
    inp.WIDTH_M, inp.DEPTH_M = 0.1, 0.1
    try:
        sim = {"id": "s2", "area": {"bbox": [80.15, 13.08, 80.20, 13.13]},
               "rainfall": {"rateMmHr": 100, "durationHr": 2},
               "_test_drains": _drains()}
        rid = eng.run_simulation("s2", sim)
        for _ in range(60):
            r = eng.get_run(rid)
            if r["status"] in ("Completed", "Failed"):
                break
            time.sleep(2)
        assert r["results"]["stats"]["floodedNodeCount"] > 0
    finally:
        inp.WIDTH_M, inp.DEPTH_M = old_w, old_d

def test_empty_drains_fails_honestly():
    from app.services.engine import swmm_runner as eng
    sim = {"id": "s3", "area": {"bbox": [0, 0, 0.01, 0.01]},
           "rainfall": {"rateMmHr": 50, "durationHr": 1}, "_test_drains": []}
    rid = eng.run_simulation("s3", sim)
    for _ in range(30):
        r = eng.get_run(rid)
        if r["status"] in ("Completed", "Failed"):
            break
        time.sleep(2)
    assert r["status"] == "Failed"
    assert "blocked-no-drains" in r["error"]
