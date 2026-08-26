#!/usr/bin/env python3
"""
Analyze SWMM results: continuity, flooding, mass balance
"""
import json
import re
import pathlib
import sys

def analyze_rpt(rpt_path):
    text = pathlib.Path(rpt_path).read_text(errors='ignore')
    # continuity
    runoff = re.search(r"Runoff Quantity Continuity.*?Total Precipitation.*?([0-9.\-]+).*?mm", text, re.DOTALL)
    routing = re.search(r"Flow Routing Continuity.*?Continuity Error.*?([\-0-9\.]+)\s*%", text, re.DOTALL)
    # parse volume
    # Find lines
    res={}
    m = re.search(r"Total Precipitation.*?([0-9]+\.[0-9]+)\s+([0-9]+\.[0-9]+)", text, re.DOTALL)
    if m:
        try:
            res['precip_ha_m'] = float(m.group(1)); res['precip_mm'] = float(m.group(2))
        except: pass
    m = re.search(r"Surface Runoff.*?([0-9]+\.[0-9]+)\s+([0-9]+\.[0-9]+)", text, re.DOTALL)
    if m:
        try:
            res['runoff_ha_m'] = float(m.group(1)); res['runoff_mm'] = float(m.group(2))
        except: pass
    m = re.search(r"Infiltration Loss.*?([0-9]+\.[0-9]+)\s+([0-9]+\.[0-9]+)", text, re.DOTALL)
    if m:
        try:
            res['infil_mm'] = float(m.group(2))
        except: pass
    m = re.search(r"Flow Routing Continuity.*?Wet Weather Inflow.*?([0-9]+\.[0-9]+)", text, re.DOTALL)
    if m:
        try:
            res['wet_inflow'] = float(m.group(1))
        except: pass
    # flooding
    flood_nodes=[]
    if "Node Flooding Summary" in text:
        sec = text[text.index("Node Flooding Summary"):text.index("Node Flooding Summary")+5000]
        for line in sec.splitlines():
            # lines with J00xx floating
            if line.strip().startswith("J") and len(line.split())>=6:
                parts=line.split()
                try:
                    nid=parts[0]
                    hrs=float(parts[1])
                    rate=float(parts[2])
                    flood_vol=float(parts[5]) if len(parts)>5 else 0
                    flood_nodes.append((nid, hrs, rate, flood_vol))
                except: pass
    res['flood_nodes']=flood_nodes
    res['num_flooded']=len([n for n in flood_nodes if n[1]>0])
    # link max flow
    max_flow=None; max_depth=None
    if "Link Flow Summary" in text:
        # rough parse
        pass
    # continuity errors
    errs=re.findall(r"Continuity Error.*?([\-0-9\.]+)\s*%", text)
    res['continuity_errors']=errs[:3]
    return res

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("rpt", nargs='+')
    args=p.parse_args()
    for rpt in args.rpt:
        print(f"\n=== {rpt} ===")
        r=analyze_rpt(rpt)
        print(json.dumps(r, indent=2))
        # mass balance check
        if 'precip_mm' in r and 'runoff_mm' in r:
            print(f"Mass balance: precip {r['precip_mm']:.2f} mm = runoff {r['runoff_mm']:.2f} + infil {r.get('infil_mm',0):.2f} + storage ~? ")
        print(f"Flooded nodes: {r['num_flooded']}")
        if r['flood_nodes']:
            print("Top flooded:", sorted(r['flood_nodes'], key=lambda x: x[3], reverse=True)[:3])

