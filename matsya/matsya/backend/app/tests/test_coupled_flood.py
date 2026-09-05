def test_coupled_mass_and_wb():
    from app.services.flood import generate_flood
    snaps, pngs, stats = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 100, "durationHr": 2}, width=20, height=20, steps=3)
    assert stats["maxDepth"] > 0
    assert "mass_error" in stats and stats["mass_error"] < 0.25
    assert "wbCount" in stats and "surchargedDrains" in stats
    assert pngs[0][:8] == b"\x89PNG\r\n\x1a\n"


def test_heavier_rain_deeper_or_wider():
    from app.services.flood import generate_flood
    _, _, s1 = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 20, "durationHr": 1}, width=20, height=20, steps=3)
    _, _, s2 = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 120, "durationHr": 2}, width=20, height=20, steps=3)
    assert s2["maxDepth"] >= s1["maxDepth"]
    assert s2["totalRainMm"] > s1["totalRainMm"]

def test_spill_ring_shape():
    import numpy as np
    from app.services.flood import _spill_ring
    m = np.zeros((10, 10), dtype=bool); m[4:6, 4:6] = True
    ring = _spill_ring(m, radius=1)
    assert ring is not None and ring.dtype == bool
    assert not np.any(ring & m)          # ring never overlaps the lake
    assert ring.sum() > 0                # shoreline exists
    assert _spill_ring(np.zeros((5, 5), dtype=bool)) is None  # empty mask -> None

def test_pond_volume_adds_depth():
    import numpy as np
    from app.services.flood import _pond_volume
    s = np.zeros((10, 10)); ring = np.zeros((10, 10), dtype=bool); ring[0, 0:4] = True
    mean_d = _pond_volume(s, ring, 3600.0, 900.0)   # 3600 m3 over 4 cells of 900 m2
    assert abs(mean_d - 1.0) < 1e-9
    assert abs(s[0, 0] - 1.0) < 1e-9 and s[5, 5] == 0.0

def test_heavy_rain_spills_and_stays_balanced():
    from app.services.flood import generate_flood
    _, _, stats = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 200, "durationHr": 3},
                                 width=20, height=20, steps=3)
    assert "spillVolumeM3" in stats and "overtoppedLakes" in stats
    assert stats["spillVolumeM3"] > 0.0 and stats["overtoppedLakes"] > 0
    assert stats["mass_error"] < 0.25
    _, _, light = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 20, "durationHr": 1},
                                 width=20, height=20, steps=3)
    assert light["spillVolumeM3"] <= stats["spillVolumeM3"]

def test_initial_fill_zero_starts_empty():
    from app.services.hydro.waterbody import WaterBody
    wb = WaterBody(area_m2=10000, crest=5.0, stage=5.0 - 2.0 + 0.0 * 2.0)  # 0% of 2m
    assert wb.volume == 0.0

def test_initial_fill_default_matches_legacy():
    # 75% of a 2m bucket == crest-0.5, the historic hardcode
    from app.services.hydro.waterbody import WaterBody
    wb = WaterBody(area_m2=10000, crest=5.0, stage=(5.0 - 2.0) + 0.75 * 2.0)
    assert abs(wb.stage - 4.5) < 1e-9

def test_initial_fill_hundred_spills_first():
    from app.services.flood import generate_flood
    _, _, s100 = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 5, "durationHr": 1},
                                width=10, height=10, steps=2, initial_fill_pct=100)
    _, _, s0 = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 5, "durationHr": 1},
                              width=10, height=10, steps=2, initial_fill_pct=0)
    assert s100["initialFillPct"] == 100 and s0["initialFillPct"] == 0
    assert s100["spillVolumeM3"] >= s0["spillVolumeM3"]
    assert s100["mass_error"] < 0.25 and s0["mass_error"] < 0.25

def test_river_cells_cover_polyline():
    import numpy as np
    from app.services.flood import _river_cells
    mask = _river_cells([(80.16, 13.10), (80.17, 13.11)], [80.15, 13.08, 80.20, 13.13],
                        width=20, height=20, radius_m=45)
    assert mask is not None and mask.dtype == bool and mask.sum() > 0

def test_heavy_rain_river_keys_and_mass():
    from app.services.flood import generate_flood
    _, _, s = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 200, "durationHr": 3},
                             width=20, height=20, steps=3)
    assert "riverSpillVolumeM3" in s and "overtoppedRivers" in s
    assert s["mass_error"] < 0.25
    # lake behavior must not regress: heavy rain still spills from lakes
    assert s["overtoppedLakes"] > 0 and s["spillVolumeM3"] > 0

def test_river_step_overtops_above_bankfull():
    import numpy as np
    from app.services.flood import _river_step
    from app.services.hydro.river import RiverReach
    from app.services.hydro.river_capacity import reach_capacity
    cap = reach_capacity(2000.0, 0.001, width_m=5.0, depth_m=1.5)
    reach = RiverReach(length=2000, slope=0.001)
    mask = np.zeros((10, 10), dtype=bool); mask[5, :] = True
    surface = np.zeros((10, 10))
    # below bankfull: all routed to sea, nothing ponds
    r = _river_step(reach, {"qbank": cap["qbank"]}, cap["qbank"] * 0.5 * 300, 300, surface, mask, 900.0)
    assert r["spill_vol"] == 0.0 and r["overtopped"] is False and r["sea_vol"] > 0
    assert surface.sum() == 0.0
    # above bankfull: excess ponds on the mask
    r2 = _river_step(reach, {"qbank": cap["qbank"]}, cap["qbank"] * 3.0 * 300, 300, surface, mask, 900.0)
    assert r2["overtopped"] is True and r2["spill_vol"] > 0
    assert surface[5, :].sum() > 0 and surface[0, :].sum() == 0.0

def test_swmm_coupling_keys_and_mass():
    from app.services.flood import generate_flood
    _, _, s = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 100, "durationHr": 2},
                             width=20, height=20, steps=3)
    assert "swmmCoupled" in s and "swmmFloodVolumeM3" in s
    assert s["mass_error"] < 0.25

def test_swmm_fallback_when_solver_missing():
    import app.services.flood as F
    real = F._swmm_node_floods if hasattr(F, "_swmm_node_floods") else None
    assert real is not None
    F._swmm_node_floods = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no solver"))
    try:
        _, _, s = F.generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 100, "durationHr": 2},
                                   width=20, height=20, steps=3)
        assert s["swmmCoupled"] is False and s["mass_error"] < 0.25
    finally:
        F._swmm_node_floods = real
