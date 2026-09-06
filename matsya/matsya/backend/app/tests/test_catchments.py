def test_catchments_partition_bbox():
    from app.services.hydro.catchments import delineate_catchments
    c = delineate_catchments([80.15, 13.08, 80.20, 13.13])
    assert len(c) >= 1
    total = sum(v["area_m2"] for v in c.values())
    assert 0 < total <= 29.96e6 * 1.5  # bounded by bbox area + margin

def test_buckingham_tide_series_shape():
    from app.services.hydro.catchments import buckingham_tide
    s = buckingham_tide(hours=6)
    assert len(s) == 6 and all(isinstance(v, float) for _, v in s)
