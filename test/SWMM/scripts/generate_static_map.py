#!/usr/bin/env python3
"""
Generate static PNG map of SWMM network (quick preview without HTML)
"""
import json, pathlib
import matplotlib.pyplot as plt
import matplotlib.collections as mcollections

def plot_model(json_path, png_path):
    data=json.loads(pathlib.Path(json_path).read_text())
    nodes=data['nodes']
    conduits=data['conduits']
    rpt=data['rpt_summary']
    # Create figure
    fig, ax=plt.subplots(figsize=(10,10))
    ax.set_aspect('equal')
    # Plot conduits
    for c in conduits:
        coords=c['coords']
        if len(coords)<2: continue
        lons=[p[0] for p in coords]; lats=[p[1] for p in coords]
        # color by max_flow or flooding
        # Determine if conduit touches flooded node?
        # Simple: color by capacity? Use max_flow
        max_flow=c.get('max_flow',0)
        # normalize
        # 0.01 low, 0.05 high for this scale
        if max_flow>0.05:
            color='#dc2626'
            lw=2.5
        elif max_flow>0.03:
            color='#f97316'
            lw=2
        elif max_flow>0.01:
            color='#eab308'
            lw=1.5
        else:
            color='#0ea5e9'
            lw=1.2
        ax.plot(lons, lats, color=color, linewidth=lw, alpha=0.8)
    # Plot nodes
    for n in nodes:
        if 'lon' not in n: continue
        flood=n.get('flood_summary',{})
        vol=flood.get('volume',0)
        is_flood=vol>0 or flood.get('hours',0)>0.5
        if n['type']=='outfall':
            ax.scatter(n['lon'], n['lat'], c='#a78bfa', s=60, marker='s', edgecolors='k', linewidths=0.5, zorder=3)
        else:
            if is_flood:
                ax.scatter(n['lon'], n['lat'], c='#ef4444', s=120, marker='o', edgecolors='k', linewidths=0.7, zorder=4)
            else:
                ax.scatter(n['lon'], n['lat'], c='#22c55e', s=50, marker='o', edgecolors='k', linewidths=0.5, zorder=3)
    # Annotate flooded nodes
    for n in nodes:
        flood=n.get('flood_summary',{})
        if flood.get('volume',0)>0.1:
            ax.text(n['lon']+0.00015, n['lat']+0.00012, n['id'], fontsize=6, color='#7f1d1d', weight='bold')
    ax.set_title(f"MATSYA {data['model']}\n{len(nodes)} nodes, {len(conduits)} conduits — 50 mm/hr ×1 hr — Flooded: {sum(1 for n in nodes if n.get('flood_summary',{}).get('volume',0)>0)} nodes", fontsize=12, pad=12)
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    plt.tight_layout()
    pathlib.Path(png_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(png_path, dpi=180, bbox_inches='tight')
    print(f"Saved {png_path}")
    plt.close()

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--json", required=True)
    p.add_argument("--png", required=True)
    args=p.parse_args()
    plot_model(args.json, args.png)

# Auto-run for both models
