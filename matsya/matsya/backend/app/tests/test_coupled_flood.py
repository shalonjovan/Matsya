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
