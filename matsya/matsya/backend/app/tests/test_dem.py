def test_waterbody_area():
    from app.services.hydro.asset_loader import load_assets
    from app.services.hydro.dem import enrich_waterbodies
    data=load_assets("assets")
    gdf=enrich_waterbodies(data["waterbodies"].head(5), data["dem"])
    assert "area_m2" in gdf.columns
    assert gdf.iloc[0]["area_m2"] > 1000
    assert gdf.iloc[0]["spill_crest"] is not None
    assert "centroid_lon" in gdf.columns
    assert "centroid_lat" in gdf.columns
    # check dem_elev is float or None
    assert isinstance(gdf.iloc[0]["spill_crest"], float)

def test_waterbody_area_empty():
    import geopandas as gpd
    from app.services.hydro.dem import enrich_waterbodies, waterbody_area_m2
    empty = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")
    res = enrich_waterbodies(empty, None)
    assert len(res)==0
    res2 = waterbody_area_m2(empty)
    assert len(res2)==0
