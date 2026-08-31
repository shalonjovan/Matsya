"""Graph builder for drains -> waterbodies/rivers/sea."""
import networkx as nx
import geopandas as gpd

def build_graph(snap_result: dict, waterbodies: gpd.GeoDataFrame, rivers: gpd.GeoDataFrame = None) -> nx.DiGraph:
    G = nx.DiGraph()
    mapping = snap_result.get("mapping", {})
    snapped = snap_result.get("snapped")
    # Add drain nodes
    for drain_id, target in mapping.items():
        G.add_node(f"drain:{drain_id}", type="drain", id=drain_id)
        # target is wb:xxx or river:xxx or sea
        if target.startswith("wb:"):
            wb_id = target.split(":")[1]
            G.add_node(f"wb:{wb_id}", type="waterbody", id=wb_id)
            G.add_edge(f"drain:{drain_id}", f"wb:{wb_id}", type="drain_to_wb")
        elif target.startswith("river:"):
            rid = target.split(":")[1]
            G.add_node(f"river:{rid}", type="river", id=rid)
            G.add_edge(f"drain:{drain_id}", f"river:{rid}", type="drain_to_river")
        elif target == "sea":
            G.add_node("sea", type="sea", id="sea")
            G.add_edge(f"drain:{drain_id}", "sea", type="drain_to_sea")
        else:
            G.add_node(target, type="unknown")
            G.add_edge(f"drain:{drain_id}", target)
    # Add waterbodies that have no inflow (still nodes)
    if waterbodies is not None and len(waterbodies)>0:
        for _, row in waterbodies.iterrows():
            nid = f"wb:{row['id']}" if "id" in row else f"wb:{row.name}"
            if nid not in G:
                G.add_node(nid, type="waterbody", id=row.get("id", row.name))
    # Add waterbody -> river edges where polygon touches river (within 10m)
    # For now, simple: if waterbody centroid within 100m of river, add spill edge
    # This is a stub for weir outflow
    if rivers is not None and len(rivers)>0 and waterbodies is not None and len(waterbodies)>0:
        try:
            wb_utm = waterbodies.to_crs("EPSG:32644")
            riv_utm = rivers.to_crs("EPSG:32644")
            for _, wb_row in wb_utm.iterrows():
                wb_id = f"wb:{wb_row['id']}"
                # distance to nearest river
                try:
                    dists = riv_utm.geometry.distance(wb_row.geometry.centroid)
                    if dists.min() < 100:
                        rid = riv_utm.loc[dists.idxmin(), "id"]
                        r_id = f"river:{rid}"
                        if r_id not in G:
                            G.add_node(r_id, type="river", id=rid)
                        # add spill edge if not already
                        if not G.has_edge(wb_id, r_id):
                            G.add_edge(wb_id, r_id, type="wb_to_river")
                except: pass
            # river -> sea for those near coast (bbox)
            for _, rrow in riv_utm.iterrows():
                rid = f"river:{rrow['id']}"
                # check if river end near sea (lon >80.28 and lat <12.95 approx)
                try:
                    geom = rrow.geometry
                    if geom.geom_type == "LineString":
                        end = geom.coords[-1]
                    else:
                        end = geom.centroid.coords[0]
                    # end is in 32644, convert back to 4326 for check
                    # simple: if x > 470000 (approx 80.27) and y < 1435000 (approx 12.97)
                    if end[0] > 470000 and end[1] < 1440000:
                        if not G.has_edge(rid, "sea"):
                            if "sea" not in G:
                                G.add_node("sea", type="sea")
                            G.add_edge(rid, "sea", type="river_to_sea")
                except: pass
        except: pass
    return G

def graph_stats(G: nx.DiGraph) -> dict:
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "drains_to_wb": sum(1 for _,_,d in G.edges(data=True) if d.get("type")=="drain_to_wb"),
        "drains_to_river": sum(1 for _,_,d in G.edges(data=True) if d.get("type")=="drain_to_river"),
        "drains_to_sea": sum(1 for _,_,d in G.edges(data=True) if d.get("type")=="drain_to_sea"),
    }
