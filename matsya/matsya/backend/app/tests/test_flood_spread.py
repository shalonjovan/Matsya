def _flat_gap_frac(depth, dem, gap=0.5, flat=0.1):
    import numpy as np
    depth = np.asarray(depth, dtype=float)
    dem = np.asarray(dem, dtype=float)
    pairs, gappy = 0, 0
    for dr, dc in ((0, 1), (1, 0)):
        ddem = np.abs(dem - np.roll(dem, (-dr, -dc), (0, 1)))[:-1, :-1]
        dd = np.abs(depth - np.roll(depth, (-dr, -dc), (0, 1)))[:-1, :-1]
        fl = ddem < flat
        pairs += int(fl.sum())
        gappy += int(np.logical_and(fl, dd > gap).sum())
    return gappy / max(1, pairs)


def test_storm_spreads_laterally_on_flats():
    import numpy as np
    from app.services.flood import generate_flood, _dem_for_bbox
    bbox = [80.15, 13.08, 80.20, 13.13]
    snaps, _, st = generate_flood(bbox, {"rateMmHr": 150, "durationHr": 3},
                                  width=60, height=60, steps=9)
    last = np.asarray(snaps[-1])
    dem = np.array(_dem_for_bbox(bbox, 60, 60), dtype=float)
    dem = np.where(np.isnan(dem), float(np.nanmean(dem)), dem)
    assert _flat_gap_frac(last, dem) < 0.02  # was ~0.12 with D8-only routing
    assert st["mass_error"] < 0.25


def test_point_rain_spreads_footprint():
    # rain on one spot must wet neighbours, not just deepen one cell
    import numpy as np
    from app.services.flood import generate_flood
    poly = {"type": "Polygon", "coordinates": [[[80.172, 13.102], [80.178, 13.102], [80.178, 13.108], [80.172, 13.108], [80.172, 13.102]]]}
    rf = {"rateMmHr": 0.1, "durationHr": 1,
          "zones": [{"id": "p", "amount": 300, "unit": "rate", "polygon": poly}]}
    snaps, _, st = generate_flood([80.15, 13.08, 80.20, 13.13], rf, width=40, height=40, steps=6)
    last = np.asarray(snaps[-1])
    wet = last > 0.05
    assert wet.sum() > 25  # footprint wider than the ~6x6-cell rain patch
    assert st["mass_error"] < 0.25
