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

def test_normalize_lake_name_aliases():
    from app.services.hydro.waterbody_enrich import normalize_lake_name
    assert normalize_lake_name("Madavaram eri") == "madhavaram"
    assert normalize_lake_name("Kaveripak Tank") == "kaveripakkam"
    assert normalize_lake_name("Pulal lake") == "redhills"
    assert normalize_lake_name("Ambattur tank") == "ambattur"
    assert normalize_lake_name("") == ""

def test_name_match_requires_footprint():
    import geopandas as gpd
    from shapely.geometry import box
    from app.services.hydro.waterbody_enrich import match_bathy_by_name
    # KML lake named Ambattur, far from the Ambattur raster footprint -> reject
    kml = gpd.GeoDataFrame({"DRNP_NAME": ["Ambattur tank"], "geometry": [box(0, 0, 500, 500)]}, crs="EPSG:32644")
    index = {"Ambattur_IDW": {"bounds_32644": [100000, 100000, 101000, 101000], "bed_min": 8.0, "bed_mean": 12.0}}
    assert match_bathy_by_name(kml, index) == {}

def test_name_match_accepts_inside_footprint():
    import geopandas as gpd
    from shapely.geometry import box
    from app.services.hydro.waterbody_enrich import match_bathy_by_name
    kml = gpd.GeoDataFrame({"DRNP_NAME": ["Madavaram eri"], "geometry": [box(100100, 100100, 100600, 100600)]}, crs="EPSG:32644")
    index = {"Madhavaram_IDW": {"bounds_32644": [100000, 100000, 101000, 101000], "bed_min": 7.5, "bed_mean": 11.0}}
    m = match_bathy_by_name(kml, index)
    assert 0 in m and m[0]["bathy_stem"] == "Madhavaram_IDW"
    assert m[0]["match_rule"] == "name-spatial"

def test_name_match_rejects_ambiguous():
    import geopandas as gpd
    from shapely.geometry import box
    from app.services.hydro.waterbody_enrich import match_bathy_by_name
    # Pakkam tank centroid inside BOTH candidate footprints -> ambiguous -> drop
    kml = gpd.GeoDataFrame({"DRNP_NAME": ["Pakkam tank"], "geometry": [box(100100, 100100, 100600, 100600)]}, crs="EPSG:32644")
    index = {
        "Pakkam_big_IDW": {"bounds_32644": [100000, 100000, 101000, 101000], "bed_min": 9.0, "bed_mean": 12.0},
        "Pakkam_Chitteri_IDW": {"bounds_32644": [100050, 100050, 101050, 101050], "bed_min": 9.5, "bed_mean": 12.5},
    }
    assert match_bathy_by_name(kml, index) == {}
