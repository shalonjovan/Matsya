#!/usr/bin/env python3
"""
Generate visualization data JSON for SWMM models
Reads .inp, .rpt, .out and produces data/*.json for HTML viewer
"""
import re
import json
import pathlib
import sys

def parse_inp(inp_path):
    text = pathlib.Path(inp_path).read_text(errors='ignore')
    # Simple section parser
    sections = {}
    current=None
    for line in text.splitlines():
        stripped=line.strip()
        if not stripped or stripped.startswith(';'):
            continue
        if stripped.startswith('[') and stripped.endswith(']'):
            current=stripped[1:-1].strip()
            sections[current]=[]
            continue
        if current:
            sections[current].append(line.rstrip())
    # Parse junctions, outfalls, conduits, coordinates, vertices, xsections, raingages
    nodes={}
    # Junctions
    for line in sections.get('JUNCTIONS',[]):
        if line.strip().startswith(';'): continue
        parts=line.split()
        if len(parts)<2: continue
        nid=parts[0]
        try:
            elev=float(parts[1]); maxd=float(parts[2]) if len(parts)>2 else 0
        except: elev=0; maxd=0
        nodes[nid]={'id':nid, 'elevation':elev, 'maxDepth':maxd, 'type':'junction'}
    for line in sections.get('OUTFALLS',[]):
        if line.strip().startswith(';'): continue
        parts=line.split()
        if len(parts)<2: continue
        nid=parts[0]
        try:
            elev=float(parts[1])
        except: elev=0
        nodes[nid]={'id':nid, 'elevation':elev, 'maxDepth':0, 'type':'outfall'}
    # Xsections for width/depth
    xsecs={}
    for line in sections.get('XSECTIONS',[]):
        if line.strip().startswith(';'): continue
        parts=line.split()
        if len(parts)<3: continue
        lid=parts[0]; shape=parts[1]
        try:
            geom1=float(parts[2]); geom2=float(parts[3]) if len(parts)>3 else 0
        except: geom1=0; geom2=0
        xsecs[lid]={'shape':shape, 'geom1':geom1, 'geom2':geom2}
    # Conduits
    conduits=[]
    for line in sections.get('CONDUITS',[]):
        if line.strip().startswith(';'): continue
        parts=line.split()
        if len(parts)<4: continue
        cid=parts[0]; frm=parts[1]; to=parts[2]
        try:
            length=float(parts[3]); rough=float(parts[4]) if len(parts)>4 else 0.014
        except: length=0; rough=0.014
        xs=xsecs.get(cid, {'geom1':0.5,'geom2':0.5})
        conduits.append({'id':cid, 'from':frm, 'to':to, 'length':length, 'roughness':rough, 'depth':xs['geom1'], 'width':xs['geom2']})
    # Coordinates
    coords={}
    for line in sections.get('COORDINATES',[]):
        if line.strip().startswith(';'): continue
        parts=line.split()
        if len(parts)<3: continue
        nid=parts[0]
        try:
            lon=float(parts[1]); lat=float(parts[2])
            coords[nid]=(lon,lat)
            if nid in nodes:
                nodes[nid]['lon']=lon; nodes[nid]['lat']=lat
        except: pass
    # Vertices
    verts={}
    for line in sections.get('VERTICES',[]):
        if line.strip().startswith(';'): continue
        parts=line.split()
        if len(parts)<3: continue
        cid=parts[0]
        try:
            lon=float(parts[1]); lat=float(parts[2])
            verts.setdefault(cid, []).append((lon,lat))
        except: pass
    # Assign conduit geometry: from -> vertices -> to
    for c in conduits:
        frm=c['from']; to=c['to']
        pts=[]
        if frm in coords:
            pts.append(coords[frm])
        if c['id'] in verts:
            pts.extend(verts[c['id']])
        if to in coords:
            pts.append(coords[to])
        c['coords']=pts

    # Raingage timeseries for hyetograph (parse TIMESERIES)
    timeseries=[]
    for line in sections.get('TIMESERIES',[]):
        if line.strip().startswith(';'): continue
        parts=line.split()
        if len(parts)<3: continue
        # Format: TS1 time value   (sometimes with date)
        # Our file: TS1  0:00 50.00
        # Could be: TS1  08/27/2026 00:00 0.25 etc.
        # Simplify: find time field like 0:00 or 00:00 and value
        # Parts: [TS1, 0:00, 50.00] or [TS1, 08/27/2026, 00:00, 0.25]
        try:
            # detect time token
            time_token=None; value=None
            for p in parts[1:]:
                if ':' in p:
                    time_token=p
                elif re.match(r'^[0-9.]+$', p) and time_token is not None:
                    value=float(p)
            if time_token and value is not None:
                timeseries.append((time_token, value))
        except: pass

    return nodes, conduits, timeseries, sections

def parse_rpt(rpt_path):
    text=pathlib.Path(rpt_path).read_text(errors='ignore')
    # continuity
    precip_mm=None; runoff_mm=None
    m=re.search(r"Total Precipitation.*?([0-9]+\.[0-9]+)\s+([0-9]+\.[0-9]+)", text, re.DOTALL)
    if m:
        try: precip_mm=float(m.group(2))
        except: pass
    m=re.search(r"Surface Runoff.*?([0-9]+\.[0-9]+)\s+([0-9]+\.[0-9]+)", text, re.DOTALL)
    if m:
        try: runoff_mm=float(m.group(2))
        except: pass
    # flooding summary dict
    flooding={}
    if "Node Flooding Summary" in text:
        sec=text[text.index("Node Flooding Summary"):text.index("Node Flooding Summary")+8000]
        for line in sec.splitlines():
            line=line.strip()
            if line.startswith("J") or line.startswith("OF"):
                parts=line.split()
                if len(parts)>=6:
                    try:
                        nid=parts[0]
                        hrs=float(parts[1]); rate=float(parts[2]); vol=float(parts[5]) if len(parts)>5 else 0
                        flooding[nid]={'hours':hrs,'rate':rate,'volume':vol}
                    except: pass
    # link flow summary
    link_flows={}
    if "Link Flow Summary" in text:
        sec=text[text.index("Link Flow Summary"):text.index("Link Flow Summary")+10000]
        for line in sec.splitlines():
            line=line.strip()
            if line.startswith("C"):
                parts=line.split()
                if len(parts)>=3:
                    try:
                        lid=parts[0]
                        max_flow=float(parts[2])
                        # also max_depth last column? In table, columns: Link Type |Flow| Time |Veloc| Full/Flow Full/Depth
                        # We'll try to capture velocities if present
                        link_flows[lid]={'max_flow':max_flow}
                    except: pass
    # continuity errors
    errs=re.findall(r"Continuity Error.*?([\-0-9\.]+)\s*%", text)
    return {'precip_mm':precip_mm, 'runoff_mm':runoff_mm, 'flooding':flooding, 'link_flows':link_flows, 'continuity_errors': errs[:3]}

def extract_out_series(out_path, inp_nodes, inp_conduits):
    from swmm.toolkit import output as smout
    from swmm.toolkit import shared_enum
    h=smout.init()
    try:
        smout.open(h, out_path)
    except Exception as e:
        print(f"Failed open out {out_path}: {e}")
        return None
    num_periods = smout.get_times(h, shared_enum.Time.NUM_PERIODS)
    report_step = smout.get_times(h, shared_enum.Time.REPORT_STEP)
    # Get dates
    dates=[]
    for i in range(num_periods):
        try:
            d=smout.get_date_time(h, i)
            from swmm.toolkit.output import decode_date
            decoded=decode_date(d)
            # decoded is [year,mon,day,hr,min,sec, ...] per earlier test: [2026,8,27,0,5,0,5]
            # We'll format as HH:MM
            hr=decoded[3]; minu=decoded[4]
            dates.append(f"{hr:02d}:{minu:02d}")
        except:
            dates.append(f"{i*report_step//60:02d}:{(i*report_step%3600)//60:02d}")
    # Build index maps: elem name -> index
    n_nodes = smout.get_proj_size(h)[shared_enum.ElementType.NODE]
    n_links = smout.get_proj_size(h)[shared_enum.ElementType.LINK]
    node_index={}
    for i in range(n_nodes):
        try:
            name=smout.get_elem_name(h, shared_enum.ElementType.NODE, i)
            node_index[name]=i
        except: pass
    link_index={}
    for i in range(n_links):
        try:
            name=smout.get_elem_name(h, shared_enum.ElementType.LINK, i)
            link_index[name]=i
        except: pass

    nodes_series={}
    # For each node in inp, get depth series
    for nid in inp_nodes:
        idx=node_index.get(nid)
        if idx is None:
            continue
        try:
            depth_series = smout.get_node_series(h, idx, shared_enum.NodeAttribute.INVERT_DEPTH, 0, num_periods-1)
            head_series = smout.get_node_series(h, idx, shared_enum.NodeAttribute.HYDRAULIC_HEAD, 0, num_periods-1)
            flood_series = smout.get_node_series(h, idx, shared_enum.NodeAttribute.FLOODING_LOSSES, 0, num_periods-1)
            inflow_series = smout.get_node_series(h, idx, shared_enum.NodeAttribute.TOTAL_INFLOW, 0, num_periods-1)
            nodes_series[nid]={'depth': list(map(float, depth_series)), 'head': list(map(float, head_series)), 'flood': list(map(float, flood_series)), 'inflow': list(map(float, inflow_series))}
        except Exception as e:
            # print(f"node series fail {nid}: {e}")
            pass

    links_series={}
    for conduit in inp_conduits:
        lid=conduit['id']
        idx=link_index.get(lid)
        if idx is None:
            continue
        try:
            flow_series = smout.get_link_series(h, idx, shared_enum.LinkAttribute.FLOW_RATE, 0, num_periods-1)
            depth_series = smout.get_link_series(h, idx, shared_enum.LinkAttribute.FLOW_DEPTH, 0, num_periods-1)
            vel_series = smout.get_link_series(h, idx, shared_enum.LinkAttribute.FLOW_VELOCITY, 0, num_periods-1)
            cap_series = smout.get_link_series(h, idx, shared_enum.LinkAttribute.CAPACITY, 0, num_periods-1)
            links_series[lid]={'flow': list(map(float, flow_series)), 'depth': list(map(float, depth_series)), 'velocity': list(map(float, vel_series)), 'capacity': list(map(float, cap_series))}
        except Exception as e:
            # print(f"link series fail {lid}: {e}")
            pass

    # System series for rainfall? Could get system rainfall
    sys_series={}
    try:
        # System rainfall is SystemAttribute.RAINFALL
        sys_series['rainfall'] = list(map(float, smout.get_system_series(h, shared_enum.SystemAttribute.RAINFALL, 0, num_periods-1)))
        sys_series['runoff'] = list(map(float, smout.get_system_series(h, shared_enum.SystemAttribute.RUNOFF_FLOW, 0, num_periods-1)))
        sys_series['flood'] = list(map(float, smout.get_system_series(h, shared_enum.SystemAttribute.FLOOD_LOSSES, 0, num_periods-1)))
        sys_series['outfall'] = list(map(float, smout.get_system_series(h, shared_enum.SystemAttribute.OUTFALL_FLOWS, 0, num_periods-1)))
    except Exception as e:
        print(f"sys series fail {e}")

    smout.close(h)
    return {'dates': dates, 'num_periods': num_periods, 'report_step': report_step, 'nodes_series': nodes_series, 'links_series': links_series, 'sys_series': sys_series}

def generate_viz_data(inp_path, rpt_path, out_path, output_json_path):
    nodes, conduits, timeseries, sections = parse_inp(inp_path)
    rpt_data = parse_rpt(rpt_path) if pathlib.Path(rpt_path).exists() else {}
    out_data = extract_out_series(out_path, nodes, conduits) if pathlib.Path(out_path).exists() else None

    # Center calculation
    lons=[n['lon'] for n in nodes.values() if 'lon' in n]
    lats=[n['lat'] for n in nodes.values() if 'lat' in n]
    center={'lon': sum(lons)/len(lons) if lons else 80.2, 'lat': sum(lats)/len(lats) if lats else 13.08, 'bounds': [min(lons) if lons else 80.15, min(lats) if lats else 13.05, max(lons) if lons else 80.25, max(lats) if lats else 13.15]}

    # Enrich nodes with rpt flooding
    for nid, n in nodes.items():
        if nid in rpt_data.get('flooding',{}):
            n['flood_summary']=rpt_data['flooding'][nid]
        else:
            n['flood_summary']={'hours':0,'rate':0,'volume':0}
        # also max flows for conduits
    for conduit in conduits:
        lid=conduit['id']
        if lid in rpt_data.get('link_flows',{}):
            conduit['max_flow']=rpt_data['link_flows'][lid]['max_flow']
        else:
            conduit['max_flow']=0
        # Add rpt max depth etc? Could parse but keep simple

    # Build final JSON
    data={
        'model': pathlib.Path(inp_path).stem,
        'inp': str(inp_path),
        'center': center,
        'nodes': list(nodes.values()),
        'conduits': conduits,
        'timeseries_inputs': timeseries,
        'rpt_summary': rpt_data,
        'out_series': out_data,
    }

    # Write
    pathlib.Path(output_json_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path,'w') as f:
        json.dump(data, f, indent=2)
    print(f"Wrote viz data to {output_json_path} with {len(nodes)} nodes, {len(conduits)} conduits, {out_data['num_periods'] if out_data else 0} periods")
    return data

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--inp", required=True)
    p.add_argument("--rpt", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--json", required=True)
    args=p.parse_args()
    generate_viz_data(args.inp, args.rpt, args.out, args.json)
