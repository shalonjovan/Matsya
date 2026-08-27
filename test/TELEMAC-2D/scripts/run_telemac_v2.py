#!/usr/bin/env python3
"""
Improved TELEMAC-2D prototype V0/V1 with stable boundaries and pit fill
"""
import pathlib, json, rasterio, numpy as np, time
from pathlib import Path

BASE=Path(__file__).parent.parent
INPUT=BASE/"input"
OUTPUT=BASE/"output"
DEM_TIF=INPUT/"dem_clipped.tif"
DRAIN_MASK_NPY=INPUT/"drain_mask.npy"
ROUGH_NPY=INPUT/"roughness.npy"

DX=30.0
G=9.81
RAIN_INTENSITY=50.0
RAIN_DURATION=3600
SIM_DURATION=21600
DT=0.5  # smaller for stability
REPORT_STEP=300

def load():
    with rasterio.open(DEM_TIF) as ds:
        dem=ds.read(1).astype(np.float32)
        dem[dem==-32768]=np.nan
        dem=np.nan_to_num(dem, nan=np.nanmean(dem))
        # Simple pit fill (fill depressions)
        # Do 2 iterations of filling pits deeper than neighbors
        filled=dem.copy()
        for _ in range(3):
            padded=np.pad(filled,1,mode='edge')
            for i in range(filled.shape[0]):
                for j in range(filled.shape[1]):
                    c=filled[i,j]
                    neigh=padded[i:i+3, j:j+3]
                    m=np.min(neigh)
                    if c < m -0.05:
                        filled[i,j]=m+0.01
        dem=filled
    drain=np.load(DRAIN_MASK_NPY)
    rough=np.load(ROUGH_NPY)
    return dem, drain, rough

def run_variant(dem, drain_mask, roughness, variant="V0"):
    rows,cols=dem.shape
    h=np.zeros((rows,cols),dtype=np.float32)
    qx=np.zeros((rows,cols+1),dtype=np.float32)
    qy=np.zeros((rows+1,cols),dtype=np.float32)
    # n at faces
    n_qx=np.zeros_like(qx)
    n_qy=np.zeros_like(qy)
    for j in range(cols+1):
        if j==0: n_qx[:,j]=roughness[:,0]
        elif j==cols: n_qx[:,j]=roughness[:,-1]
        else: n_qx[:,j]=(roughness[:,j-1]+roughness[:,j])/2
    for i in range(rows+1):
        if i==0: n_qy[i,:]=roughness[0,:]
        elif i==rows: n_qy[i,:]=roughness[-1,:]
        else: n_qy[i,:]=(roughness[i-1,:]+roughness[i,:])/2
    rain_rate=RAIN_INTENSITY/1000/3600
    z=dem
    snapshots=[]
    times=[]
    stats=[]
    n_steps=int(SIM_DURATION/DT)
    report_every=int(REPORT_STEP/DT)
    print(f"Running {variant} {rows}x{cols} dt={DT} steps={n_steps} drain {drain_mask.sum()}")

    # For boundary outflow, create outside z
    # Outside elevation = edge z - 0.5m drop to allow outflow
    # We'll handle in h_flow calculation for boundary faces specially

    for step in range(n_steps+1):
        t=step*DT
        rain=rain_rate if t<RAIN_DURATION else 0.0
        eta=z+h

        # Compute qx
        # interior faces 1..cols-1
        # Use vectorized for interior
        # For qx faces 1..cols-1: left eta[:,j-1], right eta[:,j]
        # For boundaries 0 and cols: left/right outside
        # Let's compute all faces via padded with outside drop

        # Create padded eta and z with outside = z_edge -0.5
        # Pad with 1 on each side, but outside row/col = z_edge -0.5, eta = outside z (dry)
        eta_padded=np.pad(eta,1,mode='edge')
        z_padded=np.pad(z,1,mode='edge')
        # Set outside ring to z -0.5 (dry, no water)
        # Top row outside
        eta_padded[0,1:-1]=z_padded[0,1:-1] -0.5 # Actually z_padded[0] is replicate of row0, set to z[0]-0.5
        z_padded[0,1:-1]=z[0,:]-0.5
        eta_padded[-1,1:-1]=z[-1,:]-0.5
        z_padded[-1,1:-1]=z[-1,:]-0.5
        eta_padded[1:-1,0]=z[:,0]-0.5
        z_padded[1:-1,0]=z[:,0]-0.5
        eta_padded[1:-1,-1]=z[:,-1]-0.5
        z_padded[1:-1,-1]=z[:,-1]-0.5
        # corners
        eta_padded[0,0]=z[0,0]-0.5; z_padded[0,0]=z[0,0]-0.5
        eta_padded[0,-1]=z[0,-1]-0.5; z_padded[0,-1]=z[0,-1]-0.5
        eta_padded[-1,0]=z[-1,0]-0.5; z_padded[-1,0]=z[-1,0]-0.5
        eta_padded[-1,-1]=z[-1,-1]-0.5; z_padded[-1,-1]=z[-1,-1]-0.5

        # Now qx faces: qx[i,j] corresponds to face between padded col j and j+1 at row i+1 (due to pad)
        # qx shape (rows, cols+1) corresponds to interior faces plus boundaries
        # Map: qx[i,j] left cell = padded row i+1 col j, right = col j+1
        eta_left_qx=eta_padded[1:-1, 0:cols+1] # rows, cols+1
        eta_right_qx=eta_padded[1:-1, 1:cols+2]
        z_left_qx=z_padded[1:-1, 0:cols+1]
        z_right_qx=z_padded[1:-1, 1:cols+2]
        slope_qx=(eta_right_qx - eta_left_qx)/DX
        h_flow_qx=np.maximum(0, np.maximum(eta_left_qx, eta_right_qx) - np.maximum(z_left_qx, z_right_qx))
        # Limit h_flow to prevent blow up
        h_flow_qx=np.clip(h_flow_qx, 0, 10)
        mask_qx=h_flow_qx>0.001
        denom=np.ones_like(qx)
        denom[mask_qx] += G*DT*(n_qx[mask_qx]**2)*np.abs(qx[mask_qx])/(h_flow_qx[mask_qx]**(7/3)+1e-8)
        qx_new=np.where(mask_qx, (qx - G*h_flow_qx*DT*slope_qx)/denom, 0)
        # Limit q to not exceed available water (CFL-ish)
        # Max q such that outflow doesn't empty cell more than h*dx/dt
        # For qx, limit |q| <= h_flow * DX / DT * 0.5 maybe
        # Apply simple limiter
        q_limit = h_flow_qx * DX / DT * 0.2  # 20% of available
        qx_new=np.clip(qx_new, -q_limit, q_limit)
        qx=qx_new

        # qy
        eta_top_qy=eta_padded[0:rows+1, 1:-1]
        eta_bottom_qy=eta_padded[1:rows+2, 1:-1]
        z_top_qy=z_padded[0:rows+1, 1:-1]
        z_bottom_qy=z_padded[1:rows+2, 1:-1]
        slope_qy=(eta_bottom_qy - eta_top_qy)/DX
        h_flow_qy=np.maximum(0, np.maximum(eta_top_qy, eta_bottom_qy) - np.maximum(z_top_qy, z_bottom_qy))
        h_flow_qy=np.clip(h_flow_qy, 0, 10)
        mask_qy=h_flow_qy>0.001
        denom_qy=np.ones_like(qy)
        denom_qy[mask_qy] += G*DT*(n_qy[mask_qy]**2)*np.abs(qy[mask_qy])/(h_flow_qy[mask_qy]**(7/3)+1e-8)
        qy_new=np.where(mask_qy, (qy - G*h_flow_qy*DT*slope_qy)/denom_qy, 0)
        q_limit_y=h_flow_qy * DX / DT *0.2
        qy_new=np.clip(qy_new, -q_limit_y, q_limit_y)
        qy=qy_new

        # Continuity
        div = (qx[:,:-1] - qx[:,1:] + qy[:-1,:] - qy[1:,:]) / DX
        h_new = h + DT*(div + rain)
        if variant=="V1":
            # Infinite drain: remove water at drain cells
            # Record volume removed
            h_new[drain_mask==1] *= 0.3  # remove 70% each step (gradual sink, more stable than 100%)
            # Alternative: h_new[drain_mask==1]=0 would be 100% removal
        h_new=np.maximum(0, h_new)
        h_new[h_new<1e-8]=0
        # Additional limiter: cap h at 5m to prevent blow up
        h_new=np.clip(h_new, 0, 5)
        h=h_new

        if step % report_every==0:
            max_h=np.max(h)
            mean_h=np.mean(h[h>0]) if np.any(h>0) else 0
            flooded=np.sum(h>0.05)
            vol=np.sum(h)*DX*DX
            max_vel=np.max(np.sqrt(qx[:,:-1]**2 + qy[:-1,:]**2)/(np.maximum(h,0.01))) if np.any(h>0) else 0
            print(f"[{variant} {t/3600:.2f}hr] max_h {max_h:.3f} mean {mean_h:.3f} flood {flooded}/{h.size} vol {vol:.1f} vel {max_vel:.2f} rain {rain*1000*3600:.1f}")
            snapshots.append(h.copy())
            times.append(t)
            stats.append({'t':t,'max_h':float(max_h),'mean_h':float(mean_h),'flooded':int(flooded),'vol':float(vol)})

        if np.max(h)>5:
            print("Cap hit, continuing but capped")

    return {'h_final':h, 'snapshots':snapshots, 'times':times, 'stats':stats, 'dem':z, 'drain_mask':drain_mask}

if __name__=="__main__":
    dem,drain,rough=load()
    for var in ["V0","V1"]:
        print(f"\n=== {var} ===")
        res=run_variant(dem,drain,rough,variant=var)
        out=Path(f"test/TELEMAC-2D/output/{var}")
        out.mkdir(parents=True, exist_ok=True)
        with rasterio.open(DEM_TIF) as src:
            prof=src.profile
        h_final=res['h_final']
        prof.update(dtype='float32',count=1,compress='lzw',nodata=-9999)
        with rasterio.open(out/f"depth_final_{var}.tif",'w',**prof) as dst:
            dst.write(h_final.astype(np.float32),1)
        np.save(out/f"snapshots_{var}.npy", np.array(res['snapshots']))
        np.save(out/f"times_{var}.npy", np.array(res['times']))
        import json
        with open(out/f"stats_{var}.json",'w') as f:
            json.dump(res['stats'],f,indent=2)
        print(f"Saved {var}")

