def test_backwater_chokes_drains_vs_free():
    from app.services.engine.backwater import iterate_backwater
    # same FIXED-outfall code path, only the head differs. A high river stage
    # must flood the street (node flood volume up) vs a deeply-low stage.
    # (Outfall *outflow* is the wrong metric: fixed heads drive circulation.)
    free = iterate_backwater([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 100, "durationHr": 2},
                             {"force_river_stage_m": -10.0})
    choked = iterate_backwater([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 100, "durationHr": 2},
                               {"force_river_stage_m": 8.0})
    assert free["converged"] is True
    assert choked["node_flood_volume_m3"] > free["node_flood_volume_m3"]
