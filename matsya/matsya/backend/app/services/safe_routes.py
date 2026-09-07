"""Flood-safe routing over road segments (stdlib only, no networkx).

Graph nodes are segment endpoints plus pairwise segment crossings; edges
carry the parent segment's per-step depth series. Routing is earliest-arrival
Dijkstra: an edge entered at minute m uses step floor(m / mpf), blocked when
depth >= threshold. Speed default 30 km/h urban (documented assumption).
"""
import heapq
import math

SPEED_M_PER_MIN = 500.0
SNAP_TOL_M = 200.0

_GRAPH_CACHE: dict = {}


def _haversine_m(lon1, lat1, lon2, lat2):
    try:
        _r = 6371000.0
        _p1, _p2 = math.radians(lat1), math.radians(lat2)
        _a = math.sin(math.radians(lat2 - lat1) / 2) ** 2 + \
            math.cos(_p1) * math.cos(_p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
        return 2 * _r * math.asin(min(1.0, math.sqrt(max(0.0, _a))))
    except Exception:
        return 0.0


def build_graph(sim, bbox, series_by_id):
    """Nodes/edges from segment midpoints chained along parent roads.

    Full crossing-split needs segment polylines (Phase A stores midpoints
    only), so the graph chains same-road segments in file order and links
    nearby endpoints across roads (< 120m). Returns (nodes, adj) where
    nodes = {nid: (lon, lat)}, adj = {nid: [(nbr, edge)]} and
    edge = {"segmentId", "lengthM", "series"}.
    """
    nodes: dict = {}
    adj: dict = {}
    try:
        from app.services.road_segments import build_segments
        segs, _ = build_segments(list(bbox))
    except Exception:
        return {}, {}
    if not segs:
        return {}, {}
    # chain same-road segments in order
    _by_road: dict = {}
    for s in segs:
        _by_road.setdefault(s.get("roadId"), []).append(s)
    _nid = 0

    def _add_node(lon, lat):
        nonlocal _nid
        _key = (round(lon, 6), round(lat, 6))
        for _id, _pos in nodes.items():
            if _pos == _key:
                return _id
        _nid += 1
        nodes[_nid] = _key
        adj[_nid] = []
        return _nid

    for _road, _ss in _by_road.items():
        _prev = None
        for s in _ss:
            try:
                _m = s["midpoint"]
                _n = _add_node(float(_m["lon"]), float(_m["lat"]))
                if _prev is not None:
                    _e = {"segmentId": s["segmentId"], "lengthM": float(s.get("lengthM") or 0.0),
                          "series": (series_by_id or {}).get(s["segmentId"], [])}
                    adj[_prev].append((_n, _e))
                    adj[_n].append((_prev, _e))
                _prev = _n
            except Exception:
                continue
    # cross-link nearby endpoints across roads (120m) so the graph connects
    _ids = list(nodes.keys())
    for _i in range(len(_ids)):
        for _j in range(_i + 1, len(_ids)):
            try:
                _a, _b = nodes[_ids[_i]], nodes[_ids[_j]]
                if _haversine_m(_a[0], _a[1], _b[0], _b[1]) <= 120.0:
                    _e = {"segmentId": None, "lengthM": _haversine_m(_a[0], _a[1], _b[0], _b[1]),
                          "series": []}
                    adj[_ids[_i]].append((_ids[_j], _e))
                    adj[_ids[_j]].append((_ids[_i], _e))
            except Exception:
                continue
    return nodes, adj


def snap_point(nodes, lat, lon):
    """Nearest node id within SNAP_TOL_M, else None."""
    best, bestd = None, SNAP_TOL_M
    for _nid, (_x, _y) in (nodes or {}).items():
        try:
            _d = _haversine_m(lon, lat, _x, _y)
            if _d <= bestd:
                bestd, best = _d, _nid
        except Exception:
            continue
    return best


def _edge_blocked(edge, arrival_min, mpf, threshold_cm):
    try:
        _ser = edge.get("series") or []
        if not _ser:
            return False
        _k = int(math.floor(float(arrival_min) / max(1e-9, float(mpf))))
        _k = max(0, min(len(_ser) - 1, _k))
        return float(_ser[_k].get("depthCm", 0.0)) >= float(threshold_cm)
    except Exception:
        return False


def _edge_max_depth(edge, arrival_min, mpf):
    try:
        _ser = edge.get("series") or []
        if not _ser:
            return 0.0
        _k = int(math.floor(float(arrival_min) / max(1e-9, float(mpf))))
        _k = max(0, min(len(_ser) - 1, _k))
        return float(_ser[_k].get("depthCm", 0.0))
    except Exception:
        return 0.0


def earliest_arrival(nodes, adj, src, dst, depart_min, mpf, threshold_cm, respect_flood):
    """Dijkstra earliest arrival. Returns (etaMin, path node ids, edges) or None."""
    try:
        _inf = float("inf")
        _dist = {src: float(depart_min)}
        _prev: dict = {}
        _pq = [(float(depart_min), src)]
        while _pq:
            _t, _u = heapq.heappop(_pq)
            if _t > _dist.get(_u, _inf):
                continue
            if _u == dst:
                break
            for _v, _e in (adj.get(_u) or []):
                try:
                    if respect_flood and _edge_blocked(_e, _t, mpf, threshold_cm):
                        continue
                    _nt = _t + float(_e.get("lengthM") or 0.0) / SPEED_M_PER_MIN
                    if _nt < _dist.get(_v, _inf):
                        _dist[_v] = _nt
                        _prev[_v] = (_u, _e)
                        heapq.heappush(_pq, (_nt, _v))
                except Exception:
                    continue
        if dst not in _prev and dst != src:
            return None
        _path, _edges, _cur = [dst], [], dst
        while _cur != src:
            _pu, _pe = _prev[_cur]
            _path.append(_pu)
            _edges.append(_pe)
            _cur = _pu
        _path.reverse()
        _edges.reverse()
        return _dist[dst], _path, _edges
    except Exception:
        return None


def _route_summary(nodes, res, mpf, threshold_cm, depart_min):
    _eta, _path, _edges = res
    _seg_ids = [e.get("segmentId") for e in _edges if e.get("segmentId")]
    _t = float(depart_min)
    _peak = 0.0
    for _e in _edges:
        _peak = max(_peak, _edge_max_depth(_e, _t, mpf))
        _t += float(_e.get("lengthM") or 0.0) / SPEED_M_PER_MIN
    return {"path": [[nodes[n][0], nodes[n][1]] for n in _path],
            "segmentIds": _seg_ids,
            "etaMin": round(float(_eta) - float(depart_min), 1),
            "maxDepthCm": round(_peak, 1)}


def find_routes(sim, bbox, origin, destination, depart_min=0.0, threshold_cm=15.0):
    """Returns dict with fastest/safest routes or honest failure reasons."""
    from app.services.road_segments import segment_series
    from app.services.snapshots import load_snapshots
    try:
        snaps, mpf, _bb = load_snapshots(sim)
        _bbox = list(bbox) if bbox else list(_bb)
    except Exception as e:
        return {"fastest": None, "safest": None, "reason": f"snapshots unavailable: {e}"}
    try:
        rows, _meta = segment_series(sim, bbox=list(_bbox), thresholdCm=float(threshold_cm),
                                     minPeakCm=0.0, limit=4000)
    except Exception as e:
        return {"fastest": None, "safest": None, "reason": f"segments unavailable: {e}"}
    _by_id = {s["segmentId"]: s.get("series") or [] for s in rows}
    _sid = sim.get("id") if isinstance(sim, dict) else getattr(sim, "id", "?")
    _key = (_sid, len(rows))
    _cached = _GRAPH_CACHE.get("key")
    if _cached != _key:
        nodes, adj = build_graph(sim, list(_bbox), _by_id)
        _GRAPH_CACHE["key"] = _key
        _GRAPH_CACHE["graph"] = (nodes, adj)
    else:
        nodes, adj = _GRAPH_CACHE["graph"]
        # refresh series on cached topology (cheap, keeps depths current)
        for _edges in adj.values():
            for _i, (_nbr, _e) in enumerate(_edges):
                try:
                    if _e.get("segmentId") and _e["segmentId"] in _by_id:
                        _e["series"] = _by_id[_e["segmentId"]]
                except Exception:
                    continue
    if not nodes:
        return {"fastest": None, "safest": None, "reason": "no routable roads in bbox"}
    try:
        _src = snap_point(nodes, float(origin["lat"]), float(origin["lon"]))
        _dst = snap_point(nodes, float(destination["lat"]), float(destination["lon"]))
    except Exception:
        return {"fastest": None, "safest": None, "reason": "invalid origin/destination"}
    if _src is None:
        return {"fastest": None, "safest": None, "reason": "origin outside routable network (200m)"}
    if _dst is None:
        return {"fastest": None, "safest": None, "reason": "destination outside routable network (200m)"}
    _fast = earliest_arrival(nodes, adj, _src, _dst, depart_min, mpf, threshold_cm, False)
    _safe = earliest_arrival(nodes, adj, _src, _dst, depart_min, mpf, threshold_cm, True)
    if _fast is None:
        return {"fastest": None, "safest": None, "reason": "no connected path (network gap)"}
    _f = _route_summary(nodes, _fast, mpf, threshold_cm, depart_min)
    _f["floodDelayMin"] = 0.0
    _f["avoidedSegments"] = []
    if _safe is None:
        return {"fastest": _f, "safest": None, "reason": "destination cut off by flooding"}
    _s = _route_summary(nodes, _safe, mpf, threshold_cm, depart_min)
    _s["floodDelayMin"] = round(_s["etaMin"] - _f["etaMin"], 1)
    _fset, _sset = set(_f["segmentIds"]), set(_s["segmentIds"])
    _s["avoidedSegments"] = sorted(_fset - _sset)
    return {"fastest": _f, "safest": _s, "reason": None}
