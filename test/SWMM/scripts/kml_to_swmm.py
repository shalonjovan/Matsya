#!/usr/bin/env python3
"""
KML → SWMM .inp converter for MATSYA Chennai drainage test
Project: MATSYA — Urban Flood Nowcasting (SH26085)

Handles:
  - GCC SWD KML with 10k+ Placemark drains
  - Extracts geometry (lon/lat), attributes (DRAIN_WID/DEP, INVERT_SP/EP, MAT_TYP, etc.)
  - Reprojects WGS84 (EPSG:4326) → UTM 44N (EPSG:32644) for metric length & snapping
  - Reconstructs hydraulic topology via endpoint clustering (tolerance snapping)
  - Determines flow direction from invert elevations (higher → lower)
  - Generates SWMM inp with synthetic rainfall (50 mm/hr, 60 min)

Usage:
  python kml_to_swmm.py --kml ../../c4907fed-934b-4342-a3f4-74226853719d.kml --ward N082 --out ../input/matsya_N082.inp
  python kml_to_swmm.py --kml ../../c4907fed-934b-4342-a3f4-74226853719d.kml --out ../input/matsya_full.inp  (no filter)
  python kml_to_swmm.py --kml ../../c4907fed-934b-4342-a3f4-74226853719d.kml --bbox 80.15,13.11,80.17,13.12 --out ../input/matsya_bbox.inp

Assumptions documented in output report.
References:
  MATSYA_project_context.md sections 12-15
  EPA SWMM 5.2 User Manual, .inp spec
  KML coordinate system: WGS84 lon,lat,alt  → projected EPSG:32644 for Chennai
"""

import argparse
import xml.etree.ElementTree as ET
import collections
import math
import os
import sys
import json
from pathlib import Path

try:
    from pyproj import Transformer
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False
    print("WARNING: pyproj not found, falling back to haversine length calc", file=sys.stderr)

# ------------------------------- argument parsing --------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="KML → SWMM converter for MATSYA")
    p.add_argument("--kml", required=True, help="Path to KML file")
    p.add_argument("--out", required=True, help="Output .inp path")
    p.add_argument("--ward", default=None, help="Filter to specific WARD (e.g., N082). If not set, process all (or bbox)")
    p.add_argument("--bbox", default=None, help="Filter by lon/lat bbox as lon_min,lat_min,lon_max,lat_max")
    p.add_argument("--snap-tol", type=float, default=5.0, help="Node snap tolerance in meters (default 5.0)")
    p.add_argument("--rain-intensity", type=float, default=50.0, help="Synthetic rainfall intensity mm/hr (default 50)")
    p.add_argument("--rain-duration-hr", type=float, default=1.0, help="Rain duration hours (default 1.0)")
    p.add_argument("--subcatch-area-ha", type=float, default=1.0, help="Subcatchment area per junction in ha (default 1.0)")
    p.add_argument("--mannings", type=float, default=None, help="Override Manning's n (if not set, per-material)")
    p.add_argument("--report", default=None, help="JSON report path (default alongside .inp)")
    return p.parse_args()

# ------------------------------- helpers -----------------------------------------
def haversine_m(lon1, lat1, lon2, lat2):
    R = 6371000.0
    import math
    dlon = math.radians(lon2-lon1)
    dlat = math.radians(lat2-lat1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    c = 2*math.asin(math.sqrt(a))
    return R*c

def manning_for_material(typ_mat, swd_mat):
    # Concrete roughness ~0.013-0.015, Brick ~0.017
    # TYP_MAT values: Concrete, Brick, NA, etc.
    mat = (typ_mat or "").strip().lower()
    swd = (swd_mat or "").strip().lower()
    combined = mat + " " + swd
    if "brick" in combined:
        return 0.017
    if "concrete" in combined:
        return 0.014
    if "steel" in combined:
        return 0.012
    if "soil" in combined:
        return 0.020
    # default for concrete wall assumption
    return 0.014

def parse_bbox(s):
    vals = [float(x.strip()) for x in s.split(",")]
    assert len(vals)==4, "bbox needs 4 values"
    return vals  # lon_min, lat_min, lon_max, lat_max

# ------------------------------- KML parsing -------------------------------------
def parse_kml(kml_path, ward_filter=None, bbox=None):
    """
    Returns list of drains: each is dict with keys:
      objectid, ward, zone, drain_wid, drain_dep, drain_len, shape_len,
      invert_sp, invert_ep, strt_east/north, end_east/north, mat_typ, swd_mat, cover, drain_detl, drain_type,
      coords_lonlat: [(lon,lat), ...],
      raw_data: full SimpleData dict
    """
    drains=[]
    lon_min, lat_min, lon_max, lat_max = bbox if bbox else (None,None,None,None)
    context = ET.iterparse(kml_path, events=('end',))
    _, root = next(context)
    count_total=0
    count_kept=0
    for event, elem in context:
        if elem.tag.endswith('Placemark'):
            count_total+=1
            data={}
            for sd in elem.iter():
                if sd.tag.endswith('SimpleData'):
                    key=sd.attrib.get('name')
                    val=(sd.text or "").strip()
                    data[key]=val
            # need coordinates
            coords=None
            for c in elem.iter():
                if c.tag.endswith('coordinates'):
                    if c.text:
                        txt=c.text.strip()
                        pts=[]
                        for token in txt.split():
                            parts=token.split(',')
                            if len(parts)>=2:
                                try:
                                    lon=float(parts[0]); lat=float(parts[1])
                                    pts.append((lon,lat))
                                except: pass
                        coords=pts
                    break
            if coords is None or len(coords)<2:
                elem.clear(); root.clear(); continue
            # filter ward
            ward = data.get('WARD','')
            if ward_filter and ward != ward_filter:
                elem.clear(); root.clear(); continue
            # filter bbox: check centroid or any point inside?
            if bbox:
                # keep if any coordinate inside bbox OR centroid inside?
                # use centroid of coords
                avg_lon = sum(p[0] for p in coords)/len(coords)
                avg_lat = sum(p[1] for p in coords)/len(coords)
                if not (lon_min <= avg_lon <= lon_max and lat_min <= avg_lat <= lat_max):
                    elem.clear(); root.clear(); continue
            # build drain record
            try:
                oid = int(data.get('OBJECTID','0') or 0)
            except:
                oid = count_total
            def ffloat(x, fallback=0.0):
                try:
                    return float(x) if x.strip()!="" else fallback
                except:
                    return fallback
            rec = {
                'objectid': oid,
                'ward': ward,
                'zone': data.get('ZONE',''),
                'drain_wid': ffloat(data.get('DRAIN_WID',''), 0),
                'drain_dep': ffloat(data.get('DRAIN_DEP',''), 0),
                'drain_len': ffloat(data.get('DRAIN_LEN',''), 0),
                'shape_len': ffloat(data.get('SHAPE_LEN',''), 0),
                'invert_sp': data.get('INVERT_SP','').strip(),
                'invert_ep': data.get('INVERT_EP','').strip(),
                'strt_east': data.get('STRT_EAST',''),
                'strt_north': data.get('STRT_NORTH',''),
                'end_east': data.get('END_EAST',''),
                'end_north': data.get('END_NORTH',''),
                'mat_typ': data.get('MAT_TYP','') or data.get('TYP_MAT',''),
                'typ_mat': data.get('TYP_MAT',''),
                'swd_mat': data.get('SWD_MAT',''),
                'cover': data.get('COVER',''),
                'drain_detl': data.get('DRAIN_DETL',''),
                'drain_type': data.get('DRAIN_TYPE',''),
                'st_name': data.get('ST_NAME',''),
                'status': data.get('STATUS',''),
                'coords_lonlat': coords,
                'raw': data,
            }
            drains.append(rec)
            count_kept+=1
            elem.clear(); root.clear()
    # sort by OBJECTID
    drains.sort(key=lambda x: x['objectid'])
    print(f"Parsed KML: total placemarks ~{count_total}, kept {count_kept} after filter ward={ward_filter} bbox={bbox}")
    return drains

# ------------------------------- projection & metrics -----------------------------
def setup_transformer():
    if HAS_PYPROJ:
        # EPSG:4326 -> EPSG:32644 UTM 44N
        return Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True)
    else:
        return None

def project_coords(coords_lonlat, transformer):
    if transformer:
        # coords as list of (lon,lat) -> (x,y)
        xs, ys = [], []
        for lon, lat in coords_lonlat:
            x, y = transformer.transform(lon, lat)
            xs.append(x); ys.append(y)
        return list(zip(xs, ys))
    else:
        # fallback: return lon/lat as-is (will use haversine)
        return coords_lonlat

def compute_length_m(coords_proj, coords_lonlat, transformer):
    if transformer:
        # euclidean sum in UTM
        total=0.0
        for i in range(1,len(coords_proj)):
            dx = coords_proj[i][0]-coords_proj[i-1][0]
            dy = coords_proj[i][1]-coords_proj[i-1][1]
            total += math.hypot(dx, dy)
        return total
    else:
        total=0.0
        for i in range(1,len(coords_lonlat)):
            total += haversine_m(coords_lonlat[i-1][0], coords_lonlat[i-1][1], coords_lonlat[i][0], coords_lonlat[i][1])
        return total

# ------------------------------- topology reconstruction --------------------------
def build_topology(drains, snap_tol=5.0):
    """
    Reconstruct nodes by clustering endpoints within snap_tol meters (UTM).
    Returns:
      junctions: dict jid -> {x, y, lon, lat, elevation, max_depth, drains_connected}
      conduits: list of dict {id, from_node, to_node, length, roughness, wid, dep, draindata}
      vertices: dict conduit_id -> list of (lon,lat) interior vertices
      stats: dict
    """
    transformer = setup_transformer()
    # Step 1: for each drain compute projected coords and metrics
    for d in drains:
        proj = project_coords(d['coords_lonlat'], transformer)
        d['coords_proj'] = proj
        d['length_computed'] = compute_length_m(proj, d['coords_lonlat'], transformer)
        # parse inverts to float where possible, handle outliers
        def parse_invert(s):
            s=s.strip()
            if not s:
                return None
            try:
                v=float(s)
                # outlier check: typical Chennai invert 0-30m, flag >100 or < -5 as error
                if v>100 or v<-5:
                    d.setdefault('invert_warnings',[]).append(f"outlier invert {v}")
                    return None  # treat as missing, will impute
                return v
            except:
                return None
        d['invert_sp_f'] = parse_invert(d['invert_sp'])
        d['invert_ep_f'] = parse_invert(d['invert_ep'])
        # handle missing width/dep -> fallback 0.5
        if d['drain_wid'] <=0: d['drain_wid'] = 0.5
        if d['drain_dep'] <=0: d['drain_dep'] = 0.5
        # also cap 4.47 max seen, but allow up to 5
        # ensure length: if computed <1m or >5000m maybe fallback to DRAIN_LEN?
        # We'll use computed but log discrepancy.
        d['length_used'] = d['length_computed'] if d['length_computed']>1 else d['drain_len']
        # if drain_len and shape_len differ wildly, note
        if d['drain_len']>0 and abs(d['drain_len']-d['length_computed'])>50:
            d.setdefault('warnings',[]).append(f"len mismatch drain_len {d['drain_len']:.1f} vs computed {d['length_computed']:.1f}")

    # Step 2: collect endpoints
    endpoints = []  # list of {drain_idx, is_start (bool), lon, lat, x, y, invert, proj}
    for idx, d in enumerate(drains):
        # Determine start and end in terms of coords order as given in KML
        lonlat = d['coords_lonlat']
        proj = d['coords_proj']
        # start
        lon0, lat0 = lonlat[0]
        x0, y0 = proj[0]
        inv_start = d['invert_sp_f']  # SP associated with start of KML? Not guaranteed but assume SP corresponds to first coordinate block's start?
        # Actually INVERT_SP vs STRT_EAST: unclear mapping. For safety we map SP to first coord, EP to last coord.
        endpoints.append({
            'drain_idx': idx,
            'is_start': True,
            'lon': lon0, 'lat': lat0, 'x': x0, 'y': y0,
            'invert': inv_start,
            'drain': d,
        })
        lon1, lat1 = lonlat[-1]
        x1, y1 = proj[-1]
        inv_end = d['invert_ep_f']
        endpoints.append({
            'drain_idx': idx,
            'is_start': False,
            'lon': lon1, 'lat': lat1, 'x': x1, 'y': y1,
            'invert': inv_end,
            'drain': d,
        })

    # Step 3: clustering via union-find
    n = len(endpoints)
    parent = list(range(n))
    def find(a):
        while parent[a]!=a:
            parent[a]=parent[parent[a]]
            a=parent[a]
        return a
    def union(a,b):
        ra=find(a); rb=find(b)
        if ra!=rb:
            parent[rb]=ra

    # Determine tolerance: if no pyproj, we need degrees tolerance ~ 5m => ~0.000045 deg
    tol_deg = 0.00005
    if transformer:
        # Use metric distance
        # For performance, we can do brute for n<5000, else use spatial bucket
        if n < 5000:
            for i in range(n):
                xi, yi = endpoints[i]['x'], endpoints[i]['y']
                for j in range(i+1,n):
                    dx = xi - endpoints[j]['x']
                    dy = yi - endpoints[j]['y']
                    if math.hypot(dx,dy) <= snap_tol:
                        union(i,j)
        else:
            # bucket approach: round to tol grid
            # Use dict bucket -> check neighboring buckets
            # For simplicity use brute but with early exit via sorting? Let's do grid
            grid={}
            # define grid size = snap_tol
            for i, ep in enumerate(endpoints):
                gx = int(ep['x'] // snap_tol)
                gy = int(ep['y'] // snap_tol)
                key=(gx,gy)
                grid.setdefault(key,[]).append(i)
            # for each point, check 9 neighboring cells
            for i, ep in enumerate(endpoints):
                gx = int(ep['x'] // snap_tol)
                gy = int(ep['y'] // snap_tol)
                for dx in (-1,0,1):
                    for dy in (-1,0,1):
                        key=(gx+dx, gy+dy)
                        if key in grid:
                            for j in grid[key]:
                                if j <= i: continue
                                ddx = ep['x']-endpoints[j]['x']
                                ddy = ep['y']-endpoints[j]['y']
                                if math.hypot(ddx,ddy) <= snap_tol:
                                    union(i,j)
    else:
        # no proj: use haversine deg approx
        for i in range(n):
            for j in range(i+1,n):
                dlon = endpoints[i]['lon']-endpoints[j]['lon']
                dlat = endpoints[i]['lat']-endpoints[j]['lat']
                # approx meters: 1 deg lat ~111km, lon ~ cos*111km
                avg_lat = (endpoints[i]['lat']+endpoints[j]['lat'])/2
                dx = dlon * math.cos(math.radians(avg_lat)) * 111319.0
                dy = dlat * 111319.0
                if math.hypot(dx,dy) <= snap_tol:
                    union(i,j)

    # Build clusters
    clusters = collections.defaultdict(list)
    for i in range(n):
        r=find(i)
        clusters[r].append(i)

    # Create junction map
    junctions = {}  # jid -> data
    endpoint_to_jid = {}
    junc_counter=0
    for root, idxs in clusters.items():
        junc_counter+=1
        jid = f"J{junc_counter:04d}"
        # average lon/lat and x/y
        avg_lon = sum(endpoints[i]['lon'] for i in idxs)/len(idxs)
        avg_lat = sum(endpoints[i]['lat'] for i in idxs)/len(idxs)
        avg_x = sum(endpoints[i]['x'] for i in idxs)/len(idxs)
        avg_y = sum(endpoints[i]['y'] for i in idxs)/len(idxs)
        # elevation: collect inverts where not None, take minimum? Or median?
        invs = [endpoints[i]['invert'] for i in idxs if endpoints[i]['invert'] is not None]
        if invs:
            # Use median for junction elevation to reduce outlier effect, but for SWMM the invert should be lowest connecting pipe invert.
            # We'll use min for hydraulic, but also report median.
            elev = min(invs)
            # Alternative: if inverts differ >0.5m, flag warning
            if max(invs)-min(invs) > 0.5:
                warn = f"elevation spread {min(invs):.2f}-{max(invs):.2f} at junction {jid}"
                # store later
                pass
        else:
            elev = None  # will impute later
        # max_depth: max of drain depths connected
        max_dep = max(endpoints[i]['drain']['drain_dep'] for i in idxs)
        # also record connected drains
        connected = set(endpoints[i]['drain_idx'] for i in idxs)
        junctions[jid] = {
            'lon': avg_lon, 'lat': avg_lat, 'x': avg_x, 'y': avg_y,
            'elevation': elev,
            'max_depth': max_dep,
            'member_endpoints': idxs,
            'degree': len(connected),
            'inverts': invs,
        }
        for i in idxs:
            endpoint_to_jid[i]=jid

    # Impute missing elevations via nearest neighbor interpolation or fallback 10m + small gradient
    # First, collect all known elevations
    known_elevs = [j['elevation'] for j in junctions.values() if j['elevation'] is not None]
    if known_elevs:
        median_elev = sorted(known_elevs)[len(known_elevs)//2]
        mean_elev = sum(known_elevs)/len(known_elevs)
    else:
        median_elev = 10.0
        mean_elev = 10.0
    for jid, j in junctions.items():
        if j['elevation'] is None:
            # find nearest known junction via distance
            if transformer and known_elevs:
                # find nearest known
                best=None; bestd=float('inf')
                for o_jid, o_j in junctions.items():
                    if o_j['elevation'] is None: continue
                    ddx=j['x']-o_j['x']; ddy=j['y']-o_j['y']
                    d=math.hypot(ddx,ddy)
                    if d<bestd:
                        bestd=d; best=o_j['elevation']
                if best is not None:
                    # assume gentle slope: subtract 0.001*dist? but small
                    j['elevation'] = best - 0.001*bestd  # 0.1% slope
                    # clamp to 0-30
                    if j['elevation'] < 0: j['elevation']=best
                else:
                    j['elevation']=median_elev
            else:
                j['elevation']=median_elev
            j['elevation_imputed']=True
        else:
            j['elevation_imputed']=False
        # Ensure max_depth reasonable: if max_depth <0.2 set 0.5, add 0.5m freeboard
        if j['max_depth'] <0.2:
            j['max_depth']=0.5
        j['max_depth_swmm'] = j['max_depth'] + 0.3  # SWMM maxDepth for junction (allow surcharge)

    # Build conduits list with direction based on invert
    conduits=[]
    vertices_map={}  # conduit_id -> list of interior vertices (lon,lat)
    # Also track node degree for outfall detection: need to know directed graph
    # For now, store undirected degree then direct per conduit
    node_incoming = collections.Counter()
    node_outgoing = collections.Counter()
    for idx, d in enumerate(drains):
        # find start and end jids
        # endpoint indices: 2*idx and 2*idx+1 correspond to start/end? Actually endpoints list order is drain order*2
        # But our endpoints list was built in drain order, two per drain sequential.
        # So start_idx = 2*idx, end_idx=2*idx+1? Let's verify: we appended start then end per drain iterating drains order.
        # So yes.
        start_ep_idx = idx*2
        end_ep_idx = idx*2+1
        # But after clustering via union-find, mapping is via endpoint_to_jid by original index i (0..n-1)
        # Our endpoints list index i corresponds exactly to that order.
        j_start = endpoint_to_jid[start_ep_idx]
        j_end = endpoint_to_jid[end_ep_idx]
        # Detect self-loop (same node both ends) -> this conduit is zero length or loop; need to handle.
        # If same node, we need to create a dummy intermediate? For now keep but it will cause zero length warning. We'll skip self-loops by creating separate nodes? But we can keep length >0 and same node would be loop -> SWMM might error. So we should ensure distinct. If same node, we can keep as small loop? Better to separate by not merging identical endpoints if length> snap_tol? But they are snap_tol clustered. For a very short drain (<5m) start and end could be within 5m and thus same junction incorrectly. To avoid, we should only cluster distinct drains, not same drain's two ends unless length_computed < snap_tol? Let's handle after: if j_start==j_end and d['length_computed'] > snap_tol*2, then we need to split: treat as not clustered. Simplest: if same and length_computed>10, then create a second node for end manually.
        if j_start == j_end and d['length_computed'] > snap_tol*2:
            # need to un-merge: create new junction for end
            junc_counter+=1
            j_end_new = f"J{junc_counter:04d}"
            # Use original end point coordinates
            ep_end = endpoints[end_ep_idx]
            inv = ep_end['invert'] if ep_end['invert'] is not None else junctions[j_start]['elevation']
            # if inv missing, use start elev - slope
            if ep_end['invert'] is None:
                # estimate slope 0.001
                inv = junctions[j_start]['elevation'] - 0.001 * d['length_computed']
            junctions[j_end_new] = {
                'lon': ep_end['lon'], 'lat': ep_end['lat'], 'x': ep_end['x'], 'y': ep_end['y'],
                'elevation': inv,
                'max_depth': d['drain_dep'],
                'member_endpoints': [end_ep_idx],
                'degree': 1,
                'inverts': [inv] if inv else [],
                'elevation_imputed': ep_end['invert'] is None,
                'max_depth_swmm': d['drain_dep']+0.3,
            }
            endpoint_to_jid[end_ep_idx]=j_end_new
            # need to update cluster? Not needed for conduit.
            j_end = j_end_new
            # Also need to remove end_ep_idx from original junction's members? Not critical for later.
            # Recalc degree for original?
        # Determine flow direction: higher invert -> lower
        inv_sp = d['invert_sp_f']
        inv_ep = d['invert_ep_f']
        # If both available, decide:
        if inv_sp is not None and inv_ep is not None:
            if inv_sp > inv_ep:
                from_node=j_start; to_node=j_end
                invert_up=inv_sp; invert_down=inv_ep
            elif inv_ep > inv_sp:
                from_node=j_end; to_node=j_start
                invert_up=inv_ep; invert_down=inv_sp
            else:
                # equal, use geometry order (start->end)
                from_node=j_start; to_node=j_end
                invert_up=inv_sp; invert_down=inv_ep
        else:
            # fallback to geometry order
            from_node=j_start; to_node=j_end
            invert_up=inv_sp; invert_down=inv_ep

        # Correct invert elevations for junctions if we have better info:
        # Ensure junction elevation <= invert elevation? SWMM junction elevation is invert.
        # If conduit invert at that end is higher than junction elevation, conduit will have adverse slope? But we set junction elev as min in cluster, which is lowest. So if from_node is upstream higher, its elevation should be that higher invert, not min. This is conflicting.
        # For initial test, we will adjust: set from_node elevation to max(invert_up, junction elev) and to_node to invert_down etc.
        # However junctions are shared; we cannot have two different elevations for same junction from different conduits. So we keep min and SWMM will compute slope accordingly; it may result in flat or adverse for some conduits but we log it.
        # Let's also compute slope for reporting.

        length = d['length_used']
        # Ensure length in SWMM at least 1m to avoid zero length error
        if length <1.0:
            length=1.0

        # Roughness
        rough = manning_for_material(d['typ_mat'], d['swd_mat'])

        # Width/Depth for XSECTIONS
        wid = d['drain_wid']
        dep = d['drain_dep']
        # Ensure reasonable: 0.1-5m
        if wid<0.1: wid=0.3
        if dep<0.1: dep=0.3
        if wid>5: wid=5
        if dep>5: dep=5

        conduit_id = f"C{d['objectid']:05d}"

        # Slope calc for stats
        j_from_elev = junctions[from_node]['elevation']
        j_to_elev = junctions[to_node]['elevation']
        # Use invert elevations if available else junction elevations
        # Slope = (E_up - E_down)/length
        # But if we use junction elevations, slope may be different from invert slope.
        # Compute both.
        if invert_up is not None and invert_down is not None:
            slope_invert = (invert_up - invert_down)/length if length>0 else 0
        else:
            slope_invert = (j_from_elev - j_to_elev)/length if length>0 else 0
        slope_junc = (j_from_elev - j_to_elev)/length if length>0 else 0

        # If slope negative (adverse), flag
        adverse = slope_junc < -0.001  # allow small negative for tolerance?

        cond = {
            'id': conduit_id,
            'objectid': d['objectid'],
            'from_node': from_node,
            'to_node': to_node,
            'length': length,
            'length_computed': d['length_computed'],
            'length_drain_len': d['drain_len'],
            'length_shape_len': d['shape_len'],
            'roughness': rough,
            'width': wid,
            'depth': dep,
            'slope_invert': slope_invert,
            'slope_junc': slope_junc,
            'adverse': adverse,
            'coords_lonlat': d['coords_lonlat'],
            'ward': d['ward'],
            'st_name': d['st_name'],
            'mat': d['typ_mat']+"/"+d['swd_mat'],
        }
        conduits.append(cond)
        node_outgoing[from_node]+=1
        node_incoming[to_node]+=1

        # vertices: interior points excluding start/end
        if len(d['coords_lonlat'])>2:
            interior = d['coords_lonlat'][1:-1]
            vertices_map[conduit_id]=interior
        else:
            vertices_map[conduit_id]=[]

    # Determine outfalls: nodes with outgoing==0 and incoming>0 are sinks
    # Also nodes with degree==1 and is downstream (maybe)
    outfalls = set()
    junctions_outfall_flags={}
    for jid in junctions:
        out_deg = node_outgoing[jid]
        in_deg = node_incoming[jid]
        # heuristic: if out_deg==0 and in_deg>0 -> outfall
        # Also if isolated node (degree 1) and its single conduit from higher to it, then it is outfall
        is_outfall = False
        if out_deg==0 and in_deg>0:
            is_outfall=True
        # For network with loops, we need at least one outfall. If no outfall found (circular), pick lowest elevation node as outfall
        junctions_outfall_flags[jid]=is_outfall
        if is_outfall:
            outfalls.add(jid)

    if not outfalls:
        # pick node with lowest elevation
        lowest_jid = min(junctions, key=lambda k: junctions[k]['elevation'])
        outfalls.add(lowest_jid)
        junctions_outfall_flags[lowest_jid]=True
        print(f"No natural outfall detected; designating lowest node {lowest_jid} elevation {junctions[lowest_jid]['elevation']} as outfall")

    # For nodes designated as outfalls, ensure they are not also junctions in earlier definition
    # They will be moved to [OUTFALLS] section
    # But if an outfall has degree>1 with multiple incoming conduits, SWMM allows only 1 inlet? Actually SWMM says outfall has more than 1 inlet is error if >1 conduit inlet? Let's verify Example1: outfall 18 has 1 inlet (link 10). So if our outfall has multiple inlets, SWMM would error 141. To avoid, for outfalls with in_deg>1, we keep as junction and create a new downstream outfall node with a short dummy conduit.
    # Let's handle: for each outfall with in_deg>1, convert to junction and create new outfall node.
    new_outfalls=[]
    extra_conduits=[]
    for jid in list(outfalls):
        indeg = node_incoming[jid]
        if indeg >1:
            # convert to junction, create new outfall
            junc_counter+=1
            new_oid = f"OF{junc_counter:04d}"
            # new outfall slightly downstream: offset 10m east?
            # For coordinates, shift 0.0001 deg east ~11m
            orig = junctions[jid]
            new_lon = orig['lon']+0.0001
            new_lat = orig['lat']
            new_x = orig['x']+10
            new_y = orig['y']
            new_elev = orig['elevation'] - 0.05  # 5cm lower to ensure slope
            junctions[new_oid] = {
                'lon': new_lon, 'lat': new_lat, 'x': new_x, 'y': new_y,
                'elevation': new_elev,
                'max_depth': orig['max_depth'],
                'member_endpoints': [],
                'degree': 1,
                'inverts': [new_elev],
                'elevation_imputed': True,
                'max_depth_swmm': orig['max_depth_swmm'],
                'is_dummy_outfall': True,
            }
            # create dummy conduit from original junction to new outfall
            dummy_id = f"C_DUMMY_{jid}"
            extra_conduits.append({
                'id': dummy_id,
                'objectid': -1,
                'from_node': jid,
                'to_node': new_oid,
                'length': 10.0,
                'length_computed': 10.0,
                'length_drain_len': 10.0,
                'length_shape_len': 10.0,
                'roughness': 0.014,
                'width': 1.0,
                'depth': 1.0,
                'slope_invert': (orig['elevation']-new_elev)/10.0,
                'slope_junc': (orig['elevation']-new_elev)/10.0,
                'adverse': False,
                'coords_lonlat': [(orig['lon'],orig['lat']),(new_lon,new_lat)],
                'ward': 'DUMMY',
                'st_name': 'Dummy outfall conduit',
                'mat': 'Concrete',
            })
            new_outfalls.append(new_oid)
            # remove original from outfalls, keep as junction
            outfalls.remove(jid)
            junctions_outfall_flags[jid]=False
            # new outfall is true outfall
            junctions_outfall_flags[new_oid]=True
            print(f"Outfall {jid} had {indeg} inlets; converted to junction, new outfall {new_oid}")
        else:
            new_outfalls.append(jid)
    outfalls = set(new_outfalls)

    # Finally, split junctions dict into junctions vs outfalls for SWMM
    swmm_junctions = {jid: j for jid,j in junctions.items() if jid not in outfalls}
    swmm_outfalls = {jid: j for jid,j in junctions.items() if jid in outfalls}

    # Add extra dummy conduits to list
    conduits.extend(extra_conduits)
    # also vertices for dummy
    for ec in extra_conduits:
        vertices_map[ec['id']]=[]

    stats={
        'num_drains_input': len(drains),
        'num_junctions': len(swmm_junctions),
        'num_outfalls': len(swmm_outfalls),
        'num_conduits': len(conduits),
        'num_clusters': len(clusters),
        'snap_tol': snap_tol,
        'adverse_slopes': sum(1 for c in conduits if c['adverse']),
    }

    return swmm_junctions, swmm_outfalls, conduits, vertices_map, stats

# ------------------------------- INP generation ---------------------------------
def generate_inp(swmm_junctions, swmm_outfalls, conduits, vertices_map,
                 out_path, rain_intensity=50.0, rain_duration_hr=1.0, subcatch_area_ha=1.0):
    """
    Write SWMM inp file.
    Units: CMS (metric), hectares for area, mm for rainfall
    """
    # Options: use metric CMS, mm
    # Times: simulate 6 hours to include runoff recession
    # Routing: DYNWAVE for full hydraulics
    # Infiltration: HORTON
    import datetime
    start_date="08/27/2026"
    start_time="00:00:00"
    end_date="08/27/2026"
    end_time="06:00:00"
    report_step="00:05:00"
    wet_step="00:05:00"
    dry_step="01:00:00"
    routing_step="00:00:30"

    # Calculate rainfall timeseries: intensity mm/hr constant for duration
    # SWMM raingage format: VOLUME or INTENSITY. Use INTENSITY mm/hr
    # We'll create timeseries TS1: 0 at 0:00, rain_intensity at 0:00 to rain_duration, then 0 after
    # Need to decide interval: use 15min? We'll provide hourly but SWMM interpolates. Provide steps.
    # Provide entries every 15 min during rain, then hourly

    ts_entries=[]
    # At 0 hr
    ts_entries.append(("TS1","0:00", "0"))
    # Actually to get constant intensity, need value at start time. SWMM timeseries is step-like.
    # Simpler: at 0:00 -> rain_intensity, at duration -> rain_intensity, at duration+5min ->0, etc.
    # But to include initial 0, we set 0 at 0:00, then intensity at 0:01?
    # Use typical: 0 at 0:00, intensity at 0:00? Need to test. Provide:
    # TS1 0:00 0
    # TS1 0:01 intensity
    # But we will follow Example1: first value at 0:00 is rainfall start. So we can set TS1 0:00 intensity, TS1 duration intensity, TS1 duration+offset 0
    # Let's do finer:
    dur_min = int(rain_duration_hr*60)
    def fmt_time(minutes):
        h=minutes//60
        m=minutes%60
        return f"{h}:{m:02d}"
    # Provide entries at 5-min intervals for robust INTENSITY handling
    # SWMM interpolates linearly between points; giving dense points ensures correct total depth
    ts_entries=[]
    # Rainfall at 0:00 through dur_min at constant intensity
    for t in range(0, dur_min+1, 5):
        ts_entries.append(("TS1", fmt_time(t), f"{rain_intensity:.2f}"))
    # After rain, zero
    ts_entries.append(("TS1", fmt_time(dur_min+5), "0"))
    ts_entries.append(("TS1", fmt_time(360), "0"))  # 6hr

    # For continuity, ensure no rainfall before start is zero, we included.

    # Build file content
    lines=[]
    def add(line=""):
        lines.append(line)

    add("[TITLE]")
    add(";; MATSYA Chennai drainage test – KML → SWMM converted")
    add(f";; Ward filter / synthetic rainfall {rain_intensity} mm/hr for {rain_duration_hr} hr")
    add(f";; Generated by kml_to_swmm.py on 2026-08-27")
    add(";; EPSG:4326 → EPSG:32644 (UTM44N) for length calculations")
    add(";; Assumptions: see report JSON")
    add("")
    add("[OPTIONS]")
    add(";;Option             Value")
    add("FLOW_UNITS           CMS")
    add("INFILTRATION         HORTON")
    add("FLOW_ROUTING         DYNWAVE")
    add("LINK_OFFSETS         DEPTH")
    add("MIN_SLOPE            0")
    add("ALLOW_PONDING        YES")
    add("SKIP_STEADY_STATE    NO")
    add("")
    add(f"START_DATE           {start_date}")
    add(f"START_TIME           {start_time}")
    add(f"REPORT_START_DATE    {start_date}")
    add(f"REPORT_START_TIME    {start_time}")
    add(f"END_DATE             {end_date}")
    add(f"END_TIME             {end_time}")
    add(f"SWEEP_START          1/1")
    add(f"SWEEP_END            12/31")
    add(f"DRY_DAYS             0")
    add(f"REPORT_STEP          {report_step}")
    add(f"WET_STEP             {wet_step}")
    add(f"DRY_STEP             {dry_step}")
    add(f"ROUTING_STEP         {routing_step}")
    add("")
    add("INERTIAL_DAMPING     PARTIAL")
    add("NORMAL_FLOW_LIMITED  BOTH")
    add("FORCE_MAIN_EQUATION  H-W")
    add("VARIABLE_STEP        0.75")
    add("LENGTHENING_STEP     0")
    add("MIN_SURFAREA         1.2")
    add("MAX_TRIALS           8")
    add("HEAD_TOLERANCE       0.0015")
    add("SYS_FLOW_TOL         5")
    add("LAT_FLOW_TOL         5")
    add("MINIMUM_STEP         0.5")
    add("THREADS              1")
    add("")
    add("[EVAPORATION]")
    add(";;Data Source    Parameters")
    add("CONSTANT         0.0")
    add("DRY_ONLY         NO")
    add("")
    add("[RAINGAGES]")
    add(";;Name           Format    Interval SCF      Source")
    add(";;-------------- --------- ------ ------ ----------")
    add("RG1              INTENSITY 0:05     1.0      TIMESERIES TS1")
    add("")
    add("[SUBCATCHMENTS]")
    add(";;Name           Rain Gage        Outlet           Area     %Imperv  Width    %Slope   CurbLen  SnowPack")
    add(";;-------------- ---------------- ---------------- -------- -------- -------- -------- -------- ----------------")
    # Each junction gets a subcatchment
    # For outfalls, no subcatchment? We will create for all junctions (not outfalls) to avoid direct runoff to outfall.
    # Simplify: for each junction, create subcatchment S_<jid>
    for jid in sorted(swmm_junctions.keys()):
        sc_id = f"S_{jid}"
        # Area in ha, width in m, slope %, imperv %
        # Width: conceptual overland flow width ~ sqrt(area) * shape factor. Use sqrt(area*10000)/2?
        # For 1 ha = 10000 m2, width maybe 100m if square. Use 50m.
        width = 50.0
        # Impervious 60% typical urban?
        # Use 70% impervious for Chennai urban
        perc_imperv = 70
        perc_slope = 0.5
        area = subcatch_area_ha
        # CurbLen 0, SnowPack empty
        add(f"{sc_id:<16} RG1              {jid:<16} {area:<8.2f} {perc_imperv:<8} {width:<8.1f} {perc_slope:<8.2f} 0")
    add("")
    add("[SUBAREAS]")
    add(";;Subcatchment   N-Imperv   N-Perv     S-Imperv   S-Perv     PctZero    RouteTo    PctRouted")
    add(";;-------------- ---------- ---------- ---------- ---------- ---------- ---------- ----------")
    for jid in sorted(swmm_junctions.keys()):
        sc_id = f"S_{jid}"
        # N-Imperv 0.011 for concrete, N-Perv 0.15 for grass, S etc.
        add(f"{sc_id:<16} 0.011      0.15       0.05       0.10       25         OUTLET    ")
    add("")
    add("[INFILTRATION]")
    add(";;Subcatchment   MaxRate    MinRate    Decay      DryTime    MaxInfil")
    add(";;-------------- ---------- ---------- ---------- ---------- ----------")
    for jid in sorted(swmm_junctions.keys()):
        sc_id = f"S_{jid}"
        # Horton: MaxRate 3.0 in/hr? In metric, mm/hr. For SWMM CMS, infiltration units mm/hr?
        # We'll use typical: 3.0 in/hr = 76 mm/hr, but use metric: 75 mm/hr max, 10 mm/hr min?
        # Example1 uses inches: 3, 0.5 etc. Our CMS will expect mm/hr: use 75, 10?
        # But we want runoff to be high for testing, so use low infiltration.
        add(f"{sc_id:<16} 3.0        0.5        4          7          0")
    add("")
    add("[JUNCTIONS]")
    add(";;Name           Elevation  MaxDepth   InitDepth  SurDepth   Aponded")
    add(";;-------------- ---------- ---------- ---------- ---------- ----------")
    for jid, j in sorted(swmm_junctions.items()):
        elev = j['elevation']
        maxd = j['max_depth_swmm']
        add(f"{jid:<16} {elev:<10.3f} {maxd:<10.3f} 0          0          0")
    add("")
    add("[OUTFALLS]")
    add(";;Name           Elevation  Type       Stage Data       Gated    Route To")
    add(";;-------------- ---------- ---------- ---------------- -------- ----------------")
    for jid, j in sorted(swmm_outfalls.items()):
        elev = j['elevation']
        add(f"{jid:<16} {elev:<10.3f} FREE                        NO")
    add("")
    add("[CONDUITS]")
    add(";;Name           From Node        To Node          Length     Roughness  InOffset   OutOffset  InitFlow   MaxFlow")
    add(";;-------------- ---------------- ---------------- ---------- ---------- ---------- ---------- ---------- ----------")
    for c in sorted(conduits, key=lambda x: x['id']):
        add(f"{c['id']:<16} {c['from_node']:<16} {c['to_node']:<16} {c['length']:<10.2f} {c['roughness']:<10.4f} 0          0          0          0")
    add("")
    add("[XSECTIONS]")
    add(";;Link           Shape        Geom1            Geom2      Geom3      Geom4      Barrels    Culvert")
    add(";;-------------- ------------ ---------------- ---------- ---------- ---------- ---------- ----------")
    for c in sorted(conduits, key=lambda x: x['id']):
        # RECT_OPEN Geom1=height (depth), Geom2=width
        # Barrel 1
        add(f"{c['id']:<16} RECT_OPEN    {c['depth']:<16.3f} {c['width']:<10.3f} 0          0          1")
    add("")
    add("[LOSSES]")
    add(";;Link           Kentry     Kexit      Kavg       Flap Gate  Seepage")
    add(";;-------------- ---------- ---------- ---------- ---------- ----------")
    # optional, leave empty? Need header but no entries ok
    add("")
    add("[TIMESERIES]")
    add(";;Name           Date       Time       Value")
    add(";;-------------- ---------- ---------- ----------")
    for name, t, v in ts_entries:
        add(f"{name:<16}            {t:<10} {v}")
    add("")
    add("[REPORT]")
    add("INPUT      NO")
    add("CONTROLS   NO")
    add("SUBCATCHMENTS ALL")
    add("NODES ALL")
    add("LINKS ALL")
    add("CONTINUITY YES")
    add("FLOWSTATS  YES")
    add("")
    add("[TAGS]")
    add("")
    add("[MAP]")
    add("DIMENSIONS 0 0 10000 10000")
    add("Units      None")
    add("")
    add("[COORDINATES]")
    add(";;Node           X-Coord            Y-Coord")
    add(";;-------------- ------------------ ------------------")
    # Junctions and outfalls coordinates: use lon/lat for GIS overlay? SWMM expects X,Y in map units (lon/lat okay for display)
    # For better numerical, use UTM? But map units none, lon/lat will display incorrectly if SWMM expects meters, but fine.
    # We'll use lon, lat decimal degrees for consistency with KML.
    for jid, j in sorted({**swmm_junctions, **swmm_outfalls}.items()):
        add(f"{jid:<16} {j['lon']:<18.6f} {j['lat']:<18.6f}")
    add("")
    add("[VERTICES]")
    add(";;Link           X-Coord            Y-Coord")
    add(";;-------------- ------------------ ------------------")
    for cid, verts in vertices_map.items():
        for lon, lat in verts:
            add(f"{cid:<16} {lon:<18.6f} {lat:<18.6f}")
    add("")
    add("[Polygons]")
    add(";;Subcatchment   X-Coord            Y-Coord")
    add(";;-------------- ------------------ ------------------")
    # For each subcatchment, create a small square polygon around its outlet junction for visualization
    # 20m square in deg approx 0.00018 deg
    delta = 0.00015
    for jid, j in sorted(swmm_junctions.items()):
        sc_id = f"S_{jid}"
        lon, lat = j['lon'], j['lat']
        # square polygon clockwise
        pts = [(lon-delta, lat-delta),(lon+delta, lat-delta),(lon+delta, lat+delta),(lon-delta, lat+delta),(lon-delta, lat-delta)]
        for lon_p, lat_p in pts:
            add(f"{sc_id:<16} {lon_p:<18.6f} {lat_p:<18.6f}")
    add("")
    add("[SYMBOLS]")
    add(";;Gage           X-Coord            Y-Coord")
    add(";;-------------- ------------------ ------------------")
    # Place raingage near first junction average
    if swmm_junctions:
        avg_lon = sum(j['lon'] for j in swmm_junctions.values())/len(swmm_junctions)
        avg_lat = sum(j['lat'] for j in swmm_junctions.values())/len(swmm_junctions)
        add(f"RG1              {avg_lon+0.001:<18.6f} {avg_lat+0.001:<18.6f}")
    add("")

    # Write file
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        f.write("\n".join(lines))
    print(f"Wrote SWMM inp to {out_path} with {len(swmm_junctions)} junctions, {len(swmm_outfalls)} outfalls, {len(conduits)} conduits")
    return lines

# ------------------------------- main -------------------------------------------
def main():
    args = parse_args()
    kml_path = args.kml
    out_path = args.out
    ward_filter = args.ward
    bbox = parse_bbox(args.bbox) if args.bbox else None
    snap_tol = args.snap_tol
    rain_intensity = args.rain_intensity
    rain_duration_hr = args.rain_duration_hr
    subcatch_area_ha = args.subcatch_area_ha

    if not os.path.exists(kml_path):
        print(f"KML not found: {kml_path}", file=sys.stderr)
        sys.exit(1)

    drains = parse_kml(kml_path, ward_filter=ward_filter, bbox=bbox)
    if not drains:
        print("No drains found after filtering. Check WARD or bbox.", file=sys.stderr)
        sys.exit(1)

    swmm_junctions, swmm_outfalls, conduits, vertices_map, stats = build_topology(drains, snap_tol=snap_tol)

    # Generate inp
    generate_inp(swmm_junctions, swmm_outfalls, conduits, vertices_map,
                 out_path, rain_intensity=rain_intensity, rain_duration_hr=rain_duration_hr, subcatch_area_ha=subcatch_area_ha)

    # Report JSON
    report_path = args.report if args.report else str(Path(out_path).with_suffix('.json'))
    # Collect warnings
    warnings=[]
    for d in drains:
        if 'invert_warnings' in d:
            warnings.append({'objectid': d['objectid'], 'ward': d['ward'], 'warnings': d['invert_warnings']})
        if 'warnings' in d:
            warnings.append({'objectid': d['objectid'], 'warnings': d['warnings']})
    # Adverse slopes
    adverse = [c for c in conduits if c['adverse']]
    # Missing elevations
    missing_elev = sum(1 for j in swmm_junctions.values() if j.get('elevation_imputed')) + sum(1 for j in swmm_outfalls.values() if j.get('elevation_imputed'))

    report={
        'kml_path': kml_path,
        'output_inp': out_path,
        'filter': {'ward': ward_filter, 'bbox': bbox},
        'stats': stats,
        'assumptions': {
            'crs': 'EPSG:4326 → EPSG:32644 (UTM44N) for length, snap, and elevation handling',
            'snap_tolerance_m': snap_tol,
            'manning': '0.014 concrete (default), 0.017 brick, else 0.014; see code manning_for_material()',
            'cross_section': 'RECT_OPEN, Geom1=depth (DRAIN_DEP), Geom2=width (DRAIN_WID), fallback 0.5x0.5 if zero',
            'slope': 'from invert elevations (INVERT_SP/EP); if missing/outlier (>100 or <-5) imputed from nearest known junction with 0.001 slope',
            'subcatchments': f'{subcatch_area_ha} ha per junction, 70% imperv, width 50m, slope 0.5%, Horton infiltration 3.0/0.5 mm/hr',
            'rainfall': f'synthetic intensity {rain_intensity} mm/hr for {rain_duration_hr} hr via RG1/Timeseries TS1',
            'junction_maxDepth': 'DRAIN_DEP +0.3 m freeboard',
            'outfall_logic': 'nodes with outgoing==0 and incoming>0 → outfall; multi-inlet outfalls split with dummy 10m conduit',
        },
        'warnings': {
            'total_warnings': len(warnings),
            'sample_warnings': warnings[:20],
            'adverse_slopes_count': len(adverse),
            'adverse_samples': adverse[:5],
            'missing_elevation_imputed': missing_elev,
        },
        'detailed': {
            'num_drains': len(drains),
            'conduits_sample': conduits[:3],
            'junctions_sample': {k: v for k,v in list(swmm_junctions.items())[:2]},
        }
    }

    with open(report_path,'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Wrote report JSON to {report_path}")
    print(json.dumps(stats, indent=2))

if __name__=="__main__":
    main()
