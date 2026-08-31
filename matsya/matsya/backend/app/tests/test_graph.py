def test_graph():
    from app.services.hydro.asset_loader import load_assets
    from app.services.hydro.snap import snap_drains_to_waterbodies
    from app.services.hydro.graph import build_graph, graph_stats
    data=load_assets("assets")
    snap_res=snap_drains_to_waterbodies(data["micro"], data["macro"], data["rivers"], data["waterbodies"], tol=50)
    G=build_graph(snap_res, data["waterbodies"], data["rivers"])
    assert G.number_of_nodes() > 50
    assert G.number_of_edges() > 20
    stats=graph_stats(G)
    assert stats["drains_to_wb"] == snap_res["stats"]["snapped_to_waterbody"]
    # check sea exists
    assert "sea" in G or any("sea" in n for n in G.nodes())
    # check at least one drain->wb edge
    assert stats["drains_to_wb"] > 5

def test_graph_empty():
    import networkx as nx
    from app.services.hydro.graph import build_graph
    import geopandas as gpd
    empty = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")
    G=build_graph({"mapping":{}, "snapped": empty}, empty)
    assert G.number_of_nodes()==0
