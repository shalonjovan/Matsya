#!/usr/bin/env python3
"""
Run SWMM simulation via pyswmm and produce results summary
"""
import argparse
import os
import sys
import json
from pathlib import Path

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--inp", required=True, help="Path to .inp file")
    p.add_argument("--out-dir", default=None, help="Output directory for .rpt, .out, and summary json")
    p.add_argument("--no-plot", action="store_true", help="Skip matplotlib plots")
    return p.parse_args()

def run_simulation(inp_path, out_dir=None):
    from pyswmm import Simulation, Nodes, Links, Subcatchments
    from swmm.toolkit import solver
    import tempfile

    inp_path = Path(inp_path).resolve()
    if out_dir is None:
        out_dir = inp_path.parent / "../output"
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    base = inp_path.stem
    rpt_path = out_dir / f"{base}.rpt"
    out_path = out_dir / f"{base}.out"

    # pyswmm Simulation will use inp_path and produce rpt/out in same directory as inp? Actually it uses inp path to derive rpt/out names.
    # We'll run with explicit handling: Simulation creates rpt/out alongside inp? In pyswmm, it creates temp files.
    # Instead we can use swmm.toolkit directly for control, or just use Simulation and then copy rpt.

    # Trick: pyswmm Simulation uses input file's directory for report/output; we want them in out_dir.
    # We'll create a temp copy of inp in out_dir and run there.

    import shutil
    tmp_inp = out_dir / f"{base}.inp"
    shutil.copy(inp_path, tmp_inp)
    tmp_rpt = out_dir / f"{base}.rpt"
    tmp_out = out_dir / f"{base}.out"

    print(f"Running SWMM: {tmp_inp}")
    print(f"  -> rpt: {tmp_rpt}")
    print(f"  -> out: {tmp_out}")

    # Use pyswmm Simulation
    # Note: pyswmm Simulation does not take explicit rpt/out paths, but we can manage via simulation context
    # The API: Simulation(input_file) will create report and output alongside inp with .rpt/.out extensions
    # We'll just use that.

    node_stats={}
    link_stats={}
    subcatch_stats={}
    mass_balance=None
    errors=None

    try:
        with Simulation(str(tmp_inp)) as sim:
            # Optional: step through
            step_count=0
            for step in sim:
                step_count+=1
                pass
            print(f"Completed {step_count} routing steps")

            # After simulation, we can query nodes/links if needed via Nodes(sim) but sim closed? Better query during sim.
        # For detailed results, need to use swmm.toolkit output API or read rpt.

        # Alternative: use Simulation with report writing check
        # Read rpt file
        if tmp_rpt.exists():
            rpt_text = tmp_rpt.read_text(errors='ignore')
            print(f"Report size {len(rpt_text)} chars")
            # Parse continuity etc
            # Search for continuity errors
            import re
            # Example: "Flow Routing Continuity  ...  -0.053 %"
            m = re.search(r"Flow Routing Continuity.*", rpt_text)
            if m:
                print(m.group(0))
            # Also runoff continuity
            for line in rpt_text.splitlines():
                if "Continuity" in line or "Error" in line or "Flooding" in line:
                    print(line[:200])
        else:
            print("No rpt file found")

        # Now also get mass balance via swmm_get_mass_balance if simulation kept file
        # We'll try to read binary output using swmm.toolkit.output?

        # Try to parse output file using pyswmm Output? Let's attempt
        try:
            from swmm.toolkit.output import Output
            # But output API may not be needed; just report success
        except: pass

        # Parse rpt for node/link stats sections
        # We'll extract some key numbers for JSON summary
        summary={
            'inp': str(inp_path),
            'rpt': str(tmp_rpt),
            'out': str(tmp_out),
            'status': 'success',
            'continuity': None,
            'flooding': None,
        }
        if tmp_rpt.exists():
            text=tmp_rpt.read_text(errors='ignore')
            # Find continuity section
            # Look for "Runoff Quantity Continuity" and "Flow Routing Continuity"
            import re
            # Runoff continuity
            m_run = re.search(r"Runoff Quantity Continuity.*?Total Precipitation.*?([0-9.\-]+)\s+mm", text, re.DOTALL)
            # Alternatively parse table
            # Simpler: extract lines with "***"
            # Just store head
            summary['rpt_head'] = text[:3000]
            # Find flooding summary
            # Look for "Node Flooding Summary"
            if "Node Flooding Summary" in text:
                # extract that section until next blank
                start = text.index("Node Flooding Summary")
                snippet = text[start:start+3000]
                summary['flooding_section'] = snippet
                print(snippet[:1500])
            # Find link flow summary
            if "Link Flow Summary" in text:
                start = text.index("Link Flow Summary")
                snippet = text[start:start+4000]
                summary['link_flow_section'] = snippet
            # Flow continuity
            # regex for error %
            cont_match = re.findall(r"Continuity.*?([\-0-9\.]+)\s*%", text)
            if cont_match:
                summary['continuity_errors'] = cont_match[:5]

        # Also try to use pyswmm to get detailed node depths via re-running with inspection
        # Re-run with inspection inside simulation
        node_depths={}
        link_flows={}
        try:
            with Simulation(str(tmp_inp)) as sim:
                nodes = Nodes(sim)
                links = Links(sim)
                # step and capture max
                max_depths={}
                max_flows={}
                for step in sim:
                    for nid in nodes:
                        try:
                            d = nodes[nid].depth
                            if nid not in max_depths or d > max_depths[nid]:
                                max_depths[nid]=d
                        except: pass
                    for lid in links:
                        try:
                            f = links[lid].flow
                            if lid not in max_flows or abs(f) > abs(max_flows.get(lid,0)):
                                max_flows[lid]=f
                        except: pass
                node_depths = max_depths
                link_flows = max_flows
                summary['max_node_depth'] = {k: float(v) for k,v in list(max_depths.items())[:10]}
                summary['max_link_flow'] = {k: float(v) for k,v in list(max_flows.items())[:10]}
                summary['max_depth_overall'] = max(max_depths.values()) if max_depths else None
                summary['max_flow_overall'] = max([abs(v) for v in max_flows.values()]) if max_flows else None
        except Exception as e:
            print(f"Inspection inside simulation failed: {e}")
            import traceback; traceback.print_exc()

        # Write summary json
        json_path = out_dir / f"{base}_summary.json"
        with open(json_path,'w') as jf:
            json.dump(summary, jf, indent=2, default=str)
        print(f"Wrote summary JSON to {json_path}")
        return summary

    except Exception as e:
        print(f"Simulation FAILED: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        # Try to print rpt if exists
        if tmp_rpt.exists():
            print("--- RPT content on failure ---")
            print(tmp_rpt.read_text(errors='ignore')[:5000])
        summary={'status':'failed','error': str(e)}
        json_path = out_dir / f"{base}_summary.json"
        with open(json_path,'w') as jf:
            json.dump(summary, jf, indent=2, default=str)
        raise

if __name__=="__main__":
    args=parse_args()
    run_simulation(args.inp, args.out_dir)
