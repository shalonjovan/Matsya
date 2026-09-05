def test_match_lakes_strict_guards():
    import geopandas as gpd
    from shapely.geometry import box
    from app.services.hydro.waterbody_enrich import match_lakes
    # big KML lake + same-delineation ZIP lake -> match with observed depth
    kml = gpd.GeoDataFrame({"geometry": [box(0, 0, 1000, 1000)]}, crs="EPSG:32644")
    zipg = gpd.GeoDataFrame(
        {"ID": [7], "Area_ha": [100.0], "VOL_MCM": [2.0], "LB_VOL": [1.8], "UB_VOL": [2.2],
         "geometry": [box(50, 50, 950, 950)]}, crs="EPSG:32644")
    m = match_lakes(kml, zipg)
    assert 0 in m
    assert m[0]["zip_id"] == "7"
    assert abs(m[0]["obs_depth_m"] - 2.0) < 1e-6  # 2.0 MCM / 100 ha = 2.0 m
    assert m[0]["depth_source"] == "observed-volume"

def test_match_lakes_rejects_slivers():
    import geopandas as gpd
    from shapely.geometry import box
    from app.services.hydro.waterbody_enrich import match_lakes
    # tiny 600m2 ZIP sliver inside a big KML lake must NOT match
    kml = gpd.GeoDataFrame({"geometry": [box(0, 0, 1000, 1000)]}, crs="EPSG:32644")
    zipg = gpd.GeoDataFrame(
        {"ID": [9], "Area_ha": [0.06], "VOL_MCM": [0.0018], "LB_VOL": [0.0016], "UB_VOL": [0.0022],
         "geometry": [box(100, 100, 120, 130)]}, crs="EPSG:32644")
    m = match_lakes(kml, zipg)
    assert m == {}

def test_lookup_observations_defaults_assumed():
    from app.services.hydro.waterbody_enrich import lookup_observations
    r = lookup_observations("no-such-idx", cache={"lake": {}, "bathy": {}})
    assert r["depth_source"] == "assumed"
