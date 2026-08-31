def test_snap():
    from app.services.hydro.asset_loader import load_assets
    from app.services.hydro.snap import snap_drains_to_waterbodies
    data=load_assets("assets")
    res=snap_drains_to_waterbodies(data["micro"], data["macro"], data["rivers"], data["waterbodies"], tol=50)
    total = len(data["micro"])+len(data["macro"])
    assert res["stats"]["total"] == total
    assert res["stats"]["snapped_to_waterbody"] + res["stats"]["to_river"] + res["stats"]["to_sea"] == total
    # check explicit drain 0 ends in waterbody or river or sea (not None)
    first_id = res["snapped"].iloc[0]["id"]
    assert res["mapping"][first_id] is not None
    assert res["mapping"][first_id].startswith(("wb:", "river:", "sea"))
    # unsnapped <5% (allow small tolerance)
    assert res["stats"]["unsnapped"] < 5
    # snapped should have same length as total
    assert len(res["snapped"]) == total
    print(res["stats"])

def test_snap_empty():
    import geopandas as gpd
    from app.services.hydro.snap import snap_drains_to_waterbodies
    empty = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")
    res=snap_drains_to_waterbodies(empty, empty, empty, empty, tol=50)
    assert res["stats"]["total"]==0
    assert res["mapping"]=={}
